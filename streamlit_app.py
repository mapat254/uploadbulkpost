import streamlit as st
import os
import re
import pandas as pd
import datetime
import time
import frontmatter
import yaml
import io
from pathlib import Path
from github import Github, GithubException, Auth
from github.InputFileContent import InputFileContent
from dotenv import load_dotenv

# Load environment variables if .env file exists
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Bulk Post Uploader for HOMEDECOR2",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Define color palette
PRIMARY_COLOR = "#3B82F6"  # Blue
SECONDARY_COLOR = "#14B8A6"  # Teal
ACCENT_COLOR = "#8B5CF6"  # Purple
SUCCESS_COLOR = "#10B981"  # Green
WARNING_COLOR = "#F59E0B"  # Amber
ERROR_COLOR = "#EF4444"  # Red

# Apply custom CSS
st.markdown(
    f"""
    <style>
    .main .block-container {{
        padding-top: 2rem;
        padding-bottom: 2rem;
    }}
    .stButton button {{
        background-color: {PRIMARY_COLOR};
        color: white;
        border-radius: 0.375rem;
        padding: 0.5rem 1rem;
        font-weight: 500;
        border: none;
        transition: all 0.2s ease;
    }}
    .stButton button:hover {{
        background-color: #2563EB;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }}
    .success-message {{
        color: {SUCCESS_COLOR};
        font-weight: 500;
    }}
    .warning-message {{
        color: {WARNING_COLOR};
        font-weight: 500;
    }}
    .error-message {{
        color: {ERROR_COLOR};
        font-weight: 500;
    }}
    .stProgress > div > div {{
        background-color: {SECONDARY_COLOR};
    }}
    .filename {{
        font-family: monospace;
        padding: 0.2rem 0.4rem;
        background-color: #F3F4F6;
        border-radius: 0.25rem;
        font-size: 0.875rem;
    }}
    .metadata-editor {{
        background-color: #F9FAFB;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        border: 1px solid #E5E7EB;
    }}
    .section-header {{
        font-size: 1.25rem;
        font-weight: 600;
        margin-bottom: 1rem;
        color: #111827;
        border-bottom: 1px solid #E5E7EB;
        padding-bottom: 0.5rem;
    }}
    .github-info {{
        background-color: #F3F4F6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }}
    .file-preview {{
        border: 1px solid #E5E7EB;
        border-radius: 0.5rem;
        padding: 1rem;
        background-color: white;
        margin-bottom: 1rem;
        transition: all 0.2s ease;
    }}
    .file-preview:hover {{
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }}
    .stTabs [data-baseweb="tab-list"] {{
        gap: 1rem;
    }}
    .stTabs [data-baseweb="tab"] {{
        height: 3rem;
        white-space: pre-wrap;
        background-color: white;
        border-radius: 0.5rem 0.5rem 0 0;
        padding: 0.5rem 1rem;
        font-weight: 500;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: {PRIMARY_COLOR} !important;
        color: white !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize session state variables
if 'uploaded_files' not in st.session_state:
    st.session_state.uploaded_files = []
if 'file_contents' not in st.session_state:
    st.session_state.file_contents = {}
if 'file_metadata' not in st.session_state:
    st.session_state.file_metadata = {}
if 'github_token' not in st.session_state:
    st.session_state.github_token = os.getenv("GITHUB_TOKEN", "")
if 'repo_owner' not in st.session_state:
    st.session_state.repo_owner = "mapat254"
if 'repo_name' not in st.session_state:
    st.session_state.repo_name = "HOMEDECOR2"
if 'branch' not in st.session_state:
    st.session_state.branch = "main"
if 'upload_history' not in st.session_state:
    st.session_state.upload_history = []
if 'current_tab' not in st.session_state:
    st.session_state.current_tab = 0

def parse_markdown_file(content, filename):
    """Parse a markdown file with frontmatter."""
    try:
        # Use frontmatter.parse instead of frontmatter.loads
        post = frontmatter.parse(content)
        if post is None:
            # If no frontmatter is found, create default metadata
            metadata = {
                'title': Path(filename).stem.replace('-', ' ').title(),
                'date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S %z'),
                'categories': [],
                'tags': []
            }
            content = content
        else:
            metadata = dict(post.metadata)
            content = post.content
        
        # Ensure required fields exist
        if 'title' not in metadata:
            metadata['title'] = Path(filename).stem.replace('-', ' ').title()
        
        if 'date' not in metadata:
            metadata['date'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S %z')
        
        if 'categories' not in metadata:
            metadata['categories'] = []
        
        if 'tags' not in metadata:
            metadata['tags'] = []
            
        return metadata, content
    except Exception as e:
        st.error(f"Error parsing {filename}: {str(e)}")
        return {
            'title': Path(filename).stem.replace('-', ' ').title(),
            'date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S %z'),
            'categories': [],
            'tags': []
        }, content

def validate_filename(filename):
    """Validate filename format for Jekyll posts."""
    pattern = r'^\d{4}-\d{2}-\d{2}-[a-zA-Z0-9-]+\.md$'
    return bool(re.match(pattern, filename))

def format_filename(title, date=None):
    """Format title into a valid Jekyll post filename."""
    if date is None:
        date = datetime.datetime.now().strftime('%Y-%m-%d')
    
    # Convert title to lowercase, replace spaces with hyphens
    slug = title.lower().replace(' ', '-')
    
    # Remove special characters
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    
    # Remove multiple consecutive hyphens
    slug = re.sub(r'-+', '-', slug)
    
    # Ensure the slug doesn't start or end with a hyphen
    slug = slug.strip('-')
    
    return f"{date}-{slug}.md"

def update_file_content(index):
    """Update file content with edited metadata."""
    if index >= len(st.session_state.uploaded_files):
        return
    
    filename = st.session_state.uploaded_files[index].name
    metadata = st.session_state.file_metadata[filename]
    content = st.session_state.file_contents[filename]
    
    # Create frontmatter
    frontmatter_content = yaml.dump(metadata, default_flow_style=False)
    updated_content = f"---\n{frontmatter_content}---\n\n{content}"
    
    st.session_state.file_contents[filename] = content
    
    return updated_content

def upload_to_github(files_to_upload, progress_bar):
    """Upload files to GitHub repository."""
    try:
        # Create a Github instance with the provided token
        auth = Auth.Token(st.session_state.github_token)
        g = Github(auth=auth)
        
        # Get the repository
        repo = g.get_repo(f"{st.session_state.repo_owner}/{st.session_state.repo_name}")
        
        results = []
        for i, (filename, content) in enumerate(files_to_upload):
            try:
                # Check if file already exists
                try:
                    contents = repo.get_contents(f"_posts/{filename}", ref=st.session_state.branch)
                    # File exists, update it
                    result = repo.update_file(
                        path=f"_posts/{filename}",
                        message=f"Update {filename} via Streamlit uploader",
                        content=content,
                        sha=contents.sha,
                        branch=st.session_state.branch
                    )
                    file_url = f"https://github.com/{st.session_state.repo_owner}/{st.session_state.repo_name}/blob/{st.session_state.branch}/_posts/{filename}"
                    results.append({"filename": filename, "status": "updated", "url": file_url})
                    
                except GithubException as e:
                    if e.status == 404:
                        # File doesn't exist, create it
                        result = repo.create_file(
                            path=f"_posts/{filename}",
                            message=f"Add {filename} via Streamlit uploader",
                            content=content,
                            branch=st.session_state.branch
                        )
                        file_url = f"https://github.com/{st.session_state.repo_owner}/{st.session_state.repo_name}/blob/{st.session_state.branch}/_posts/{filename}"
                        results.append({"filename": filename, "status": "created", "url": file_url})
                    else:
                        results.append({"filename": filename, "status": "error", "message": str(e)})
            except Exception as e:
                results.append({"filename": filename, "status": "error", "message": str(e)})
            
            # Update progress
            progress_bar.progress((i + 1) / len(files_to_upload))
            time.sleep(0.1)  # Small delay for visual effect
        
        return results
    
    except Exception as e:
        st.error(f"GitHub upload error: {str(e)}")
        return []

# Main layout
def main():
    st.title("📝 Bulk Post Uploader for HOMEDECOR2")
    
    tabs = st.tabs(["Upload Files", "GitHub Settings", "Upload History"])
    
    with tabs[0]:  # Upload Files tab
        st.markdown('<p class="section-header">Step 1: Upload Markdown Files</p>', unsafe_allow_html=True)
        
        uploaded_files = st.file_uploader(
            "Upload your markdown (.md) files",
            type=["md"],
            accept_multiple_files=True,
            help="You can upload multiple markdown files at once."
        )
        
        if uploaded_files:
            st.session_state.uploaded_files = uploaded_files
            
            # Process uploaded files
            for uploaded_file in uploaded_files:
                if uploaded_file.name not in st.session_state.file_contents:
                    file_content = uploaded_file.read().decode("utf-8")
                    metadata, content = parse_markdown_file(file_content, uploaded_file.name)
                    
                    st.session_state.file_contents[uploaded_file.name] = content
                    st.session_state.file_metadata[uploaded_file.name] = metadata
            
            st.markdown('<p class="section-header">Step 2: Review and Edit Files</p>', unsafe_allow_html=True)
            
            # Display uploaded files with preview and metadata editor
            for i, uploaded_file in enumerate(uploaded_files):
                filename = uploaded_file.name
                
                with st.expander(f"📄 {filename}", expanded=i==0):
                    cols = st.columns([3, 2])
                    
                    with cols[0]:
                        st.markdown(f"**Content Preview:**")
                        st.text_area(
                            "Content",
                            st.session_state.file_contents[filename],
                            height=200,
                            key=f"content_{i}",
                            on_change=lambda: None
                        )
                    
                    with cols[1]:
                        st.markdown('<div class="metadata-editor">', unsafe_allow_html=True)
                        st.markdown(f"**Metadata Editor:**")
                        
                        # Title
                        new_title = st.text_input(
                            "Title",
                            st.session_state.file_metadata[filename].get('title', ''),
                            key=f"title_{i}"
                        )
                        st.session_state.file_metadata[filename]['title'] = new_title
                        
                        # Date
                        new_date = st.text_input(
                            "Date (YYYY-MM-DD HH:MM:SS +ZZZZ)",
                            st.session_state.file_metadata[filename].get('date', ''),
                            key=f"date_{i}"
                        )
                        st.session_state.file_metadata[filename]['date'] = new_date
                        
                        # Categories
                        categories_str = ', '.join(st.session_state.file_metadata[filename].get('categories', []))
                        new_categories = st.text_input(
                            "Categories (comma separated)",
                            categories_str,
                            key=f"categories_{i}"
                        )
                        st.session_state.file_metadata[filename]['categories'] = [
                            cat.strip() for cat in new_categories.split(',') if cat.strip()
                        ]
                        
                        # Tags
                        tags_str = ', '.join(st.session_state.file_metadata[filename].get('tags', []))
                        new_tags = st.text_input(
                            "Tags (comma separated)",
                            tags_str,
                            key=f"tags_{i}"
                        )
                        st.session_state.file_metadata[filename]['tags'] = [
                            tag.strip() for tag in new_tags.split(',') if tag.strip()
                        ]
                        
                        # Validate filename
                        if not validate_filename(filename):
                            st.warning(f"Filename '{filename}' doesn't follow Jekyll post format (YYYY-MM-DD-title.md).")
                            suggested_filename = format_filename(new_title)
                            st.markdown(f"Suggested filename: <span class='filename'>{suggested_filename}</span>", unsafe_allow_html=True)
                            if st.button("Use suggested filename", key=f"rename_{i}"):
                                # We'll handle the rename during upload
                                st.session_state.file_metadata[filename]['suggested_filename'] = suggested_filename
                                st.success(f"Will be uploaded as: {suggested_filename}")
                        
                        st.markdown('</div>', unsafe_allow_html=True)
                
                # Add a subtle divider
                st.markdown('<hr style="margin: 1.5rem 0; border: 0; border-top: 1px solid #E5E7EB;">', unsafe_allow_html=True)
            
            st.markdown('<p class="section-header">Step 3: Upload to GitHub</p>', unsafe_allow_html=True)
            
            if not st.session_state.github_token:
                st.warning("Please configure your GitHub token in the 'GitHub Settings' tab before uploading.")
            else:
                if st.button("Upload Files to GitHub", type="primary"):
                    st.markdown("**Upload Progress:**")
                    
                    # Create progress bar
                    progress_bar = st.progress(0)
                    
                    # Prepare files for upload
                    files_to_upload = []
                    for uploaded_file in uploaded_files:
                        filename = uploaded_file.name
                        
                        # Check if we need to use a suggested filename
                        if 'suggested_filename' in st.session_state.file_metadata[filename]:
                            upload_filename = st.session_state.file_metadata[filename]['suggested_filename']
                            # Remove the suggested_filename from metadata
                            metadata = {k: v for k, v in st.session_state.file_metadata[filename].items() if k != 'suggested_filename'}
                        else:
                            upload_filename = filename
                            metadata = st.session_state.file_metadata[filename]
                        
                        # Create frontmatter
                        frontmatter_content = yaml.dump(metadata, default_flow_style=False)
                        content = st.session_state.file_contents[filename]
                        updated_content = f"---\n{frontmatter_content}---\n\n{content}"
                        
                        files_to_upload.append((upload_filename, updated_content))
                    
                    # Upload files
                    with st.spinner("Uploading files to GitHub..."):
                        results = upload_to_github(files_to_upload, progress_bar)
                        
                        # Store in upload history
                        for result in results:
                            st.session_state.upload_history.append({
                                **result,
                                "timestamp": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            })
                    
                    # Display results
                    if results:
                        st.markdown("**Upload Results:**")
                        for result in results:
                            filename = result["filename"]
                            status = result["status"]
                            
                            if status == "created":
                                st.markdown(f"✅ <span class='success-message'>Created:</span> <span class='filename'>{filename}</span> - [View on GitHub]({result['url']})", unsafe_allow_html=True)
                            elif status == "updated":
                                st.markdown(f"🔄 <span class='warning-message'>Updated:</span> <span class='filename'>{filename}</span> - [View on GitHub]({result['url']})", unsafe_allow_html=True)
                            else:
                                st.markdown(f"❌ <span class='error-message'>Error:</span> <span class='filename'>{filename}</span> - {result.get('message', 'Unknown error')}", unsafe_allow_html=True)
                    else:
                        st.error("Upload failed. Please check your GitHub settings and try again.")
    
    with tabs[1]:  # GitHub Settings tab
        st.markdown('<p class="section-header">GitHub Repository Settings</p>', unsafe_allow_html=True)
        
        st.markdown('<div class="github-info">', unsafe_allow_html=True)
        
        st.text_input(
            "GitHub Personal Access Token (with repo scope)",
            value=st.session_state.github_token,
            type="password",
            help="Create a token at GitHub > Settings > Developer settings > Personal access tokens",
            key="github_token_input",
            on_change=lambda: setattr(st.session_state, 'github_token', st.session_state.github_token_input)
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.text_input(
                "Repository Owner",
                value=st.session_state.repo_owner,
                help="GitHub username or organization name",
                key="repo_owner_input",
                on_change=lambda: setattr(st.session_state, 'repo_owner', st.session_state.repo_owner_input)
            )
        
        with col2:
            st.text_input(
                "Repository Name",
                value=st.session_state.repo_name,
                key="repo_name_input",
                on_change=lambda: setattr(st.session_state, 'repo_name', st.session_state.repo_name_input)
            )
        
        st.text_input(
            "Branch",
            value=st.session_state.branch,
            key="branch_input",
            on_change=lambda: setattr(st.session_state, 'branch', st.session_state.branch_input)
        )
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Test connection button
        if st.button("Test GitHub Connection"):
            with st.spinner("Testing connection..."):
                try:
                    auth = Auth.Token(st.session_state.github_token)
                    g = Github(auth=auth)
                    repo = g.get_repo(f"{st.session_state.repo_owner}/{st.session_state.repo_name}")
                    
                    # Try to get the branch
                    try:
                        branch = repo.get_branch(st.session_state.branch)
                        st.success(f"✅ Successfully connected to '{st.session_state.repo_owner}/{st.session_state.repo_name}' on branch '{st.session_state.branch}'")
                        
                        # Check if _posts directory exists
                        try:
                            posts_dir = repo.get_contents("_posts", ref=st.session_state.branch)
                            st.success(f"✅ Found '_posts' directory with {len(posts_dir)} files")
                        except GithubException:
                            st.warning("⚠️ Could not find '_posts' directory in the repository. Make sure it exists.")
                            
                    except GithubException:
                        st.error(f"❌ Branch '{st.session_state.branch}' not found. Please check branch name.")
                        
                except GithubException as e:
                    if e.status == 401:
                        st.error("❌ Authentication failed. Please check your GitHub token.")
                    elif e.status == 404:
                        st.error(f"❌ Repository '{st.session_state.repo_owner}/{st.session_state.repo_name}' not found. Please check repository owner and name.")
                    else:
                        st.error(f"❌ GitHub API error: {str(e)}")
                except Exception as e:
                    st.error(f"❌ Connection error: {str(e)}")
    
    with tabs[2]:  # Upload History tab
        st.markdown('<p class="section-header">Upload History</p>', unsafe_allow_html=True)
        
        if not st.session_state.upload_history:
            st.info("No upload history yet. Upload files to see them here.")
        else:
            # Convert history to DataFrame for better display
            history_df = pd.DataFrame(st.session_state.upload_history)
            
            # Add clickable links
            if 'url' in history_df.columns:
                history_df['view'] = history_df.apply(
                    lambda row: f'<a href="{row["url"]}" target="_blank">View on GitHub</a>' if 'url' in row and row['url'] else '', 
                    axis=1
                )
            
            # Style the status column
            history_df['styled_status'] = history_df['status'].apply(
                lambda x: f'<span class="success-message">{x}</span>' if x == 'created' else 
                         (f'<span class="warning-message">{x}</span>' if x == 'updated' else 
                          f'<span class="error-message">{x}</span>')
            )
            
            # Reorder and select columns for display
            display_columns = ['timestamp', 'filename', 'styled_status']
            if 'view' in history_df.columns:
                display_columns.append('view')
            
            # Display the table
            st.markdown(
                history_df[display_columns].to_html(escape=False, index=False),
                unsafe_allow_html=True
            )
            
            if st.button("Clear History"):
                st.session_state.upload_history = []
                st.experimental_rerun()

if __name__ == "__main__":
    main()
