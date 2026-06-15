import streamlit as st
import requests
import re
import base64

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


def github_headers(token: str) -> dict[str, str]:
    """Return standard headers for GitHub API requests."""
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }


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
        headers=github_headers(token),
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
        headers=github_headers(token),
        timeout=10,
    )
    return resp.status_code == 200


def build_openweather_template(repo_name: str) -> dict[str, str]:
    """Return starter files for a Streamlit app backed by OpenWeather."""
    readme = f'''# {repo_name}

Simple Streamlit weather app powered by the OpenWeather API.

## Local run

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Create `.streamlit/secrets.toml` from `.streamlit/secrets.toml.example`
3. Add your OpenWeather API key:
   ```toml
   OPENWEATHER_API_KEY = "your_api_key_here"
   ```
4. Start the app:
   ```bash
   streamlit run streamlit_app.py
   ```

## Streamlit Community Cloud

Add this secret in the app settings:

```toml
OPENWEATHER_API_KEY = "your_api_key_here"
```
'''

    app_code = '''import requests
import streamlit as st

st.set_page_config(page_title="Weather App", page_icon="\u2600\ufe0f", layout="centered")


def get_weather(city: str, api_key: str) -> dict | None:
    response = requests.get(
        "https://api.openweathermap.org/data/2.5/weather",
        params={
            "q": city,
            "appid": api_key,
            "units": "metric",
        },
        timeout=10,
    )
    if response.status_code == 200:
        return response.json()
    return None


st.title("OpenWeather Starter")
st.caption("A minimal Streamlit app scaffolded by GRAppBuilder")

api_key = st.secrets.get("OPENWEATHER_API_KEY", "")
if not api_key:
    st.error("Missing OPENWEATHER_API_KEY in Streamlit secrets.")
    st.stop()

city = st.text_input("City", placeholder="London")

if st.button("Get weather"):
    if not city.strip():
        st.error("Enter a city name.")
    else:
        with st.spinner("Fetching weather..."):
            weather = get_weather(city.strip(), api_key)

        if not weather:
            st.error("Unable to fetch weather data. Check the city and API key.")
        else:
            st.subheader(weather["name"])
            st.write(f"Temperature: {weather['main']['temp']} C")
            st.write(f"Feels like: {weather['main']['feels_like']} C")
            st.write(f"Condition: {weather['weather'][0]['description'].title()}")
            st.write(f"Humidity: {weather['main']['humidity']}%")
'''

    return {
        "README.md": readme,
        "streamlit_app.py": app_code,
        "requirements.txt": "streamlit>=1.35.0\nrequests>=2.31.0\n",
        ".gitignore": ".streamlit/secrets.toml\n__pycache__/\n*.pyc\n",
        ".streamlit/secrets.toml.example": 'OPENWEATHER_API_KEY = "your_api_key_here"\n',
    }


def commit_repo_file(
    token: str,
    owner: str,
    repo_name: str,
    path: str,
    content: str,
    message: str,
) -> tuple[int, dict]:
    """Create or replace a file in a GitHub repo via the contents API."""
    response = requests.put(
        f"https://api.github.com/repos/{owner}/{repo_name}/contents/{path}",
        headers=github_headers(token),
        json={
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
        },
        timeout=15,
    )
    return response.status_code, response.json()


def seed_repo_template(token: str, owner: str, repo_name: str, template_name: str) -> tuple[bool, str]:
    """Populate a newly created repo with starter files."""
    if template_name == "Blank repo":
        return True, ""

    if template_name != "OpenWeather Streamlit app":
        return False, "Unknown template selected"

    for path, content in build_openweather_template(repo_name).items():
        status_code, result = commit_repo_file(
            token=token,
            owner=owner,
            repo_name=repo_name,
            path=path,
            content=content,
            message=f"Add {template_name} starter",
        )
        if status_code not in (200, 201):
            return False, result.get("message", f"Failed writing {path}")

    return True, ""


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
    template_name = st.selectbox(
        "Starter template",
        ["Blank repo", "OpenWeather Streamlit app"],
        help="Choose whether the new repo starts empty or with a ready-to-run app.",
    )
    col1, col2 = st.columns(2)
    with col1:
        visibility = st.radio("Visibility", ["Public", "Private"], horizontal=True)
    with col2:
        auto_init = st.checkbox("Add a README", value=True)

    create_btn = st.form_submit_button("🚀 Create Repository")

if create_btn:
    repo_name = slugify(repo_display_name)
    effective_auto_init = auto_init or template_name != "Blank repo"

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
                    auto_init=effective_auto_init,
                )

            if status_code == 201:
                repo_url = result["html_url"]
                if template_name != "Blank repo":
                    with st.spinner(f"Adding the {template_name} starter..."):
                        seeded, seed_error = seed_repo_template(
                            token=token,
                            owner=user["login"],
                            repo_name=repo_name,
                            template_name=template_name,
                        )
                    if not seeded:
                        st.error(f"Repository created, but template setup failed: **{seed_error}**")
                    else:
                        st.success("Repository created and starter files added.")
                else:
                    st.success("Repository created! ✅")

                st.markdown(f"🔗 [{repo_url}]({repo_url})")
                if template_name == "OpenWeather Streamlit app":
                    st.info(
                        "Add `OPENWEATHER_API_KEY` to Streamlit Community Cloud secrets for the new repo "
                        "before deploying that generated app."
                    )
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

