import streamlit as st
import requests
import re

st.set_page_config(page_title="GRAppBuilder", page_icon="🛠️", layout="centered")

st.title("🛠️ GRAppBuilder")
st.caption("GitHub Repo & Streamlit App Builder")

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def validate_token(token: str) -> dict | None:
    """Call GitHub API to verify the token and return the user profile."""
    resp = requests.get(
        "https://api.github.com/user",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        },
        timeout=10,
    )
    if resp.status_code == 200:
        return resp.json()
    return None


def get_token() -> str | None:
    """Return token from Streamlit secrets (preferred) or session state."""
    try:
        return st.secrets["GITHUB_PAT"]
    except (KeyError, FileNotFoundError):
        return st.session_state.get("github_pat")


# ---------------------------------------------------------------------------
# Auth UI
# ---------------------------------------------------------------------------

token = get_token()

if not token:
    st.info(
        "Enter your GitHub Personal Access Token to get started. "
        "The token needs the **repo** scope to create and manage repositories."
    )
    with st.form("pat_form"):
        pat_input = st.text_input(
            "GitHub Personal Access Token",
            type="password",
            placeholder="ghp_...",
        )
        submitted = st.form_submit_button("Connect to GitHub")

    if submitted and pat_input:
        with st.spinner("Validating token..."):
            user = validate_token(pat_input)
        if user:
            st.session_state["github_pat"] = pat_input
            st.session_state["github_user"] = user
            st.success(f"Connected as **{user['login']}** ✅")
            st.rerun()
        else:
            st.error("Invalid token or insufficient permissions. Check the token and try again.")
    st.stop()

# ---------------------------------------------------------------------------
# Authenticated — show user info and proceed
# ---------------------------------------------------------------------------

# Load user profile (from session or fresh from API)
if "github_user" not in st.session_state:
    with st.spinner("Loading profile..."):
        user = validate_token(token)
    if not user:
        st.error("Stored token is no longer valid. Please reconnect.")
        st.session_state.pop("github_pat", None)
        st.rerun()
    st.session_state["github_user"] = user

user = st.session_state["github_user"]

with st.sidebar:
    st.image(user["avatar_url"], width=60)
    st.markdown(f"**{user['login']}**")
    st.caption(user.get("name") or "")
    st.divider()
    st.caption(f"🔗 [Your GitHub](https://github.com/{user['login']})")
    if st.button("Disconnect"):
        st.session_state.clear()
        st.rerun()

st.success(f"Connected to GitHub as **{user['login']}**")

# ---------------------------------------------------------------------------
# Repo creation helpers
# ---------------------------------------------------------------------------

def slugify(name: str) -> str:
    """Convert a display name to a valid GitHub repo slug."""
    name = name.strip().replace(" ", "-")
    name = re.sub(r"[^a-zA-Z0-9._-]", "", name)
    return name


def create_github_repo(token: str, name: str, description: str, private: bool, auto_init: bool) -> dict:
    """Create a new GitHub repo and return the API response dict."""
    resp = requests.post(
        "https://api.github.com/user/repos",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        },
        json={
            "name": name,
            "description": description,
            "private": private,
            "auto_init": auto_init,
        },
        timeout=15,
    )
    return resp.status_code, resp.json()


def repo_exists(token: str, owner: str, name: str) -> bool:
    """Check whether a repo already exists under the authenticated user."""
    resp = requests.get(
        f"https://api.github.com/repos/{owner}/{name}",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        },
        timeout=10,
    )
    return resp.status_code == 200


# ---------------------------------------------------------------------------
# Step 2 — Repo creation UI
# ---------------------------------------------------------------------------

st.divider()
st.subheader("📁 Create a New GitHub Repository")

with st.form("create_repo_form"):
    repo_display_name = st.text_input(
        "Repository name",
        placeholder="my-awesome-app",
        help="Letters, numbers, hyphens and underscores only.",
    )
    repo_description = st.text_area(
        "Description (optional)",
        placeholder="A short description of what this repo does.",
        height=80,
    )
    col1, col2 = st.columns(2)
    with col1:
        visibility = st.radio("Visibility", ["Public", "Private"], horizontal=True)
    with col2:
        auto_init = st.checkbox("Add a README", value=True)

    create_btn = st.form_submit_button("🚀 Create Repository")

if create_btn:
    repo_name = slugify(repo_display_name)

    if not repo_name:
        st.error("Please enter a repository name.")
    elif len(repo_name) > 100:
        st.error("Repository name must be 100 characters or fewer.")
    else:
        # Show the slug if it was cleaned up
        if repo_name != repo_display_name.strip():
            st.info(f"Name adjusted to valid slug: **{repo_name}**")

        # Check for duplicate
        if repo_exists(token, user["login"], repo_name):
            st.error(f"A repo named **{repo_name}** already exists on your account.")
        else:
            with st.spinner(f"Creating **{repo_name}**..."):
                status_code, result = create_github_repo(
                    token=token,
                    name=repo_name,
                    description=repo_description.strip(),
                    private=(visibility == "Private"),
                    auto_init=auto_init,
                )

            if status_code == 201:
                repo_url = result["html_url"]
                st.success(f"Repository created! ✅")
                st.markdown(f"🔗 [{repo_url}]({repo_url})")
                st.session_state["last_created_repo"] = result
            else:
                error_msg = result.get("message", "Unknown error")
                st.error(f"GitHub returned an error: **{error_msg}**")

# Show details of the last created repo if available
if "last_created_repo" in st.session_state:
    repo = st.session_state["last_created_repo"]
    with st.expander("📋 Last created repo details", expanded=False):
        st.json({
            "name": repo["name"],
            "url": repo["html_url"],
            "visibility": "Private" if repo["private"] else "Public",
            "default_branch": repo.get("default_branch", "main"),
            "created_at": repo.get("created_at", ""),
        })

