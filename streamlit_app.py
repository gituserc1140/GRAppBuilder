import streamlit as st
import requests
import re
import base64
import json
from urllib.parse import quote_plus

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


def get_cohere_api_key() -> str:
    """Return Cohere key from Streamlit secrets or session state."""
    try:
        return st.secrets["COHERE_API_KEY"]
    except (KeyError, FileNotFoundError):
        return st.session_state.get("cohere_api_key", "")


def get_cohere_model() -> str:
    """Return preferred Cohere model from secrets or a safe default."""
    override = st.session_state.get("cohere_model_override", "")
    if isinstance(override, str) and override.strip():
        return override.strip()

    try:
        model = st.secrets.get("COHERE_MODEL", "")
    except (KeyError, FileNotFoundError, AttributeError):
        model = ""

    model = model.strip() if isinstance(model, str) else ""
    return model or "command-a-03-2025"


def is_secret_configured(secret_name: str, session_key: str | None = None) -> bool:
    """Return whether a secret exists without exposing its value."""
    try:
        value = st.secrets.get(secret_name, "")
        if isinstance(value, str):
            if value.strip():
                return True
        elif value:
            return True
    except (KeyError, FileNotFoundError, AttributeError):
        pass

    if session_key:
        session_value = st.session_state.get(session_key, "")
        if isinstance(session_value, str):
            return bool(session_value.strip())
        return bool(session_value)

    return False


def github_headers(token: str) -> dict[str, str]:
    """Return standard headers for GitHub API requests."""
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }


def build_streamlit_cloud_links(owner: str, repo_name: str, branch: str, app_file: str) -> dict[str, str]:
    """Build Streamlit Community Cloud links for deploy and management."""
    base_url = "https://share.streamlit.io"
    repo_url = f"https://github.com/{owner}/{repo_name}"
    deploy_url = (
        f"{base_url}/deploy"
        f"?repository={quote_plus(repo_url)}"
        f"&branch={quote_plus(branch)}"
        f"&mainModule={quote_plus(app_file)}"
    )
    return {
        "cloud_home": base_url,
        "deploy": deploy_url,
        "repo": repo_url,
    }


def render_streamlit_cloud_buttons(cloud_links: dict[str, str]) -> None:
    """Render Streamlit Cloud action buttons in a consistent layout."""
    deploy_col1, deploy_col2 = st.columns(2)
    with deploy_col1:
        st.link_button("Open Streamlit Cloud", cloud_links["cloud_home"])
    with deploy_col2:
        st.link_button("Deploy this repo", cloud_links["deploy"])


def render_post_push_deploy_controls(
    owner: str,
    repo_name: str,
    selected_paths: list[str],
    branch_key: str,
    app_file_key: str,
) -> None:
    """Render branch/app inputs and Streamlit Cloud deploy links after a push."""
    preferred_app_file = "streamlit_app.py"
    py_files = [path for path in selected_paths if path.endswith(".py")]
    for candidate in ["streamlit_app.py", "app.py", "main.py"]:
        if candidate in selected_paths:
            preferred_app_file = candidate
            break
    else:
        if py_files:
            preferred_app_file = py_files[0]

    deploy_branch = st.text_input(
        "Deploy branch",
        value="main",
        key=branch_key,
    )
    deploy_app_file = st.text_input(
        "Deploy app file",
        value=preferred_app_file,
        key=app_file_key,
    )
    cloud_links = build_streamlit_cloud_links(
        owner=owner,
        repo_name=repo_name,
        branch=deploy_branch.strip() or "main",
        app_file=deploy_app_file.strip() or "streamlit_app.py",
    )
    render_streamlit_cloud_buttons(cloud_links)


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

    st.divider()
    st.markdown("**Secrets Status**")
    github_status = "Configured" if is_secret_configured("GITHUB_PAT", "github_pat") else "Missing"
    cohere_status = "Configured" if is_secret_configured("COHERE_API_KEY", "cohere_api_key") else "Missing"
    st.caption(f"GITHUB_PAT: {github_status}")
    st.caption(f"COHERE_API_KEY: {cohere_status}")
    st.caption("Secret values are never displayed.")

    st.divider()
    st.markdown("**Deploy to Streamlit Cloud**")
    default_sidebar_repo = st.session_state.get("last_created_repo", {}).get("name", "")
    sidebar_repo = st.text_input(
        "Repository name",
        value=default_sidebar_repo,
        key="sidebar_streamlit_repo",
        placeholder="Example: GRAppBuilder",
    )
    sidebar_branch = st.text_input(
        "Branch",
        value="main",
        key="sidebar_streamlit_branch",
    )
    sidebar_entry_file = st.text_input(
        "App file",
        value="streamlit_app.py",
        key="sidebar_streamlit_entry_file",
    )
    if sidebar_repo.strip():
        cloud_links = build_streamlit_cloud_links(
            owner=user["login"],
            repo_name=sidebar_repo.strip(),
            branch=sidebar_branch.strip() or "main",
            app_file=sidebar_entry_file.strip() or "streamlit_app.py",
        )
        render_streamlit_cloud_buttons(cloud_links)
        st.caption("After GitHub push, Streamlit apps on this branch typically auto-redeploy.")

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


def ask_cohere_for_streamlit_help(
    api_key: str,
    user_prompt: str,
    history: list[dict[str, str]],
) -> tuple[bool, str]:
    """Call Cohere Chat API for Streamlit-focused coding help."""
    preamble = (
        "You are an expert Streamlit coding assistant inside GRAppBuilder. "
        "Help users design and build Streamlit apps. "
        "Prefer concise, practical guidance with copy-ready code blocks. "
        "When useful, provide sections: Plan, Files to create/update, and Code. "
        "Do not provide terminal git push workflows. "
        "If the user asks to push code, instruct them to use Generate file bundle mode and approve push in the app UI."
    )

    ok, payload_or_error = call_cohere_chat(
        api_key=api_key,
        payload={
            "preamble": preamble,
            "chat_history": history,
            "message": user_prompt,
            "temperature": 0.3,
        },
        timeout=45,
    )
    if not ok:
        return False, payload_or_error

    return True, payload_or_error.get("text", "No response returned.")


def call_cohere_chat(api_key: str, payload: dict, timeout: int) -> tuple[bool, dict | str]:
    """Call Cohere chat API with model fallback for retired models."""
    preferred_model = get_cohere_model()
    model_candidates: list[str] = []
    for candidate in [preferred_model, "command-a-03-2025"]:
        if candidate and candidate not in model_candidates:
            model_candidates.append(candidate)

    last_error = "Unknown Cohere API error"
    for model in model_candidates:
        response = requests.post(
            "https://api.cohere.com/v1/chat",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={**payload, "model": model},
            timeout=timeout,
        )

        if response.status_code == 200:
            return True, response.json()

        try:
            error_message = response.json().get("message", response.text)
        except ValueError:
            error_message = response.text

        last_error = f"{model}: {error_message}"

        # Auth and permission issues should not be retried with a different model.
        if response.status_code in (401, 403):
            return False, f"Cohere API error ({response.status_code}): {last_error}"

    return False, f"Cohere API error: {last_error}"


def extract_json_object(text: str) -> dict | None:
    """Extract a JSON object from plain text or fenced markdown."""
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", text)
    candidate = fenced.group(1) if fenced else text.strip()
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    # Fallback: extract the largest plausible JSON object from mixed text.
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(candidate[start:end + 1])
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None

    return None


def ask_cohere_for_file_bundle(api_key: str, user_prompt: str, context: str) -> tuple[bool, str, dict | None]:
    """Ask Cohere for a structured file bundle and parse JSON output."""
    preamble = (
        "You are an expert Streamlit app generator. "
        "Return only valid JSON with this exact shape: "
        "{\"summary\": string, \"files\": [{\"path\": string, \"content\": string}], "
        "\"notes\": [string]}. "
        "Do not include markdown fences or extra text. "
        "Generate complete, runnable files for a Streamlit app."
    )

    ok, payload_or_error = call_cohere_chat(
        api_key=api_key,
        payload={
            "preamble": preamble,
            "message": (
                f"Build request:\n{user_prompt.strip()}\n\n"
                f"Context:\n{context.strip() if context.strip() else 'None'}"
            ),
            "temperature": 0.2,
        },
        timeout=60,
    )
    if not ok:
        return False, payload_or_error, None

    output_text = payload_or_error.get("text", "")
    parsed = extract_json_object(output_text)
    if not parsed:
        # Retry once with a strict conversion pass to reduce user-facing failures.
        strict_message = (
            "Rewrite the following into VALID JSON only with this shape: "
            "{\"summary\": string, \"files\": [{\"path\": string, \"content\": string}], \"notes\": [string]}. "
            "Do not include markdown fences or explanations.\n\n"
            f"Content to convert:\n{output_text}"
        )
        retry_ok, retry_payload_or_error = call_cohere_chat(
            api_key=api_key,
            payload={
                "preamble": "You are a strict JSON formatter.",
                "message": strict_message,
                "temperature": 0.0,
            },
            timeout=45,
        )
        if not retry_ok:
            return False, retry_payload_or_error, None

        repaired_text = retry_payload_or_error.get("text", "")
        parsed = extract_json_object(repaired_text)
        if not parsed:
            return False, "Model output was not valid JSON after retry. Try adding clearer app requirements.", None

    return True, "", parsed


def validate_generated_bundle(bundle: dict) -> list[str]:
    """Return validation errors for generated file bundles."""
    errors: list[str] = []
    files = bundle.get("files")

    if not isinstance(files, list) or not files:
        return ["Bundle must include a non-empty 'files' list."]

    seen_paths: set[str] = set()
    for idx, item in enumerate(files, start=1):
        if not isinstance(item, dict):
            errors.append(f"File entry #{idx} is not an object.")
            continue

        path = item.get("path")
        content = item.get("content")

        if not isinstance(path, str) or not path.strip():
            errors.append(f"File entry #{idx} has an invalid path.")
            continue
        if path.startswith("/") or ".." in path.split("/"):
            errors.append(f"Path '{path}' is unsafe.")
        if path in seen_paths:
            errors.append(f"Path '{path}' is duplicated.")
        seen_paths.add(path)

        if not isinstance(content, str) or not content.strip():
            errors.append(f"Path '{path}' has empty content.")
            continue

        if path.endswith(".py"):
            try:
                compile(content, path, "exec")
            except SyntaxError as exc:
                errors.append(f"Python syntax error in {path}: line {exc.lineno} {exc.msg}")

    return errors


def get_repo_file_sha(token: str, owner: str, repo_name: str, path: str) -> str | None:
    """Return current blob SHA for a file in a GitHub repo, if it exists."""
    response = requests.get(
        f"https://api.github.com/repos/{owner}/{repo_name}/contents/{path}",
        headers=github_headers(token),
        timeout=15,
    )
    if response.status_code == 200:
        return response.json().get("sha")
    return None


def commit_repo_file(
    token: str,
    owner: str,
    repo_name: str,
    path: str,
    content: str,
    message: str,
    sha: str | None = None,
) -> tuple[int, dict]:
    """Create or replace a file in a GitHub repo via the contents API."""
    payload = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
    }
    if sha:
        payload["sha"] = sha

    response = requests.put(
        f"https://api.github.com/repos/{owner}/{repo_name}/contents/{path}",
        headers=github_headers(token),
        json=payload,
        timeout=15,
    )
    return response.status_code, response.json()


def upsert_repo_file(
    token: str,
    owner: str,
    repo_name: str,
    path: str,
    content: str,
    message: str,
) -> tuple[int, dict]:
    """Create or update a file in GitHub by sending SHA when needed."""
    sha = get_repo_file_sha(token, owner, repo_name, path)
    return commit_repo_file(token, owner, repo_name, path, content, message, sha=sha)


def list_user_repos(token: str) -> tuple[int, list[dict] | dict]:
    """Return repositories accessible by the authenticated user."""
    response = requests.get(
        "https://api.github.com/user/repos",
        headers=github_headers(token),
        params={
            "per_page": 100,
            "sort": "updated",
            "affiliation": "owner,collaborator,organization_member",
        },
        timeout=20,
    )
    try:
        data = response.json()
    except ValueError:
        data = {"message": response.text}
    return response.status_code, data


def list_repo_branches(token: str, owner: str, repo_name: str) -> tuple[int, list[dict] | dict]:
    """Return branches for a specific repository."""
    response = requests.get(
        f"https://api.github.com/repos/{owner}/{repo_name}/branches",
        headers=github_headers(token),
        params={"per_page": 100},
        timeout=20,
    )
    try:
        data = response.json()
    except ValueError:
        data = {"message": response.text}
    return response.status_code, data


def list_repo_files(token: str, owner: str, repo_name: str, branch: str) -> tuple[int, list[dict] | dict]:
    """Return all tracked files for a branch using the git tree API."""
    # Resolve branch to commit SHA.
    branch_resp = requests.get(
        f"https://api.github.com/repos/{owner}/{repo_name}/branches/{branch}",
        headers=github_headers(token),
        timeout=20,
    )
    if branch_resp.status_code != 200:
        try:
            return branch_resp.status_code, branch_resp.json()
        except ValueError:
            return branch_resp.status_code, {"message": branch_resp.text}

    commit_sha = branch_resp.json().get("commit", {}).get("sha")
    if not commit_sha:
        return 400, {"message": "Unable to resolve branch commit SHA."}

    tree_resp = requests.get(
        f"https://api.github.com/repos/{owner}/{repo_name}/git/trees/{commit_sha}",
        headers=github_headers(token),
        params={"recursive": "1"},
        timeout=30,
    )
    try:
        data = tree_resp.json()
    except ValueError:
        data = {"message": tree_resp.text}

    if tree_resp.status_code != 200:
        return tree_resp.status_code, data

    entries = data.get("tree", []) if isinstance(data, dict) else []
    files = [
        {
            "path": item.get("path", ""),
            "size": item.get("size", 0),
        }
        for item in entries
        if isinstance(item, dict) and item.get("type") == "blob"
    ]
    return 200, files


def get_repo_file_content(token: str, owner: str, repo_name: str, path: str, ref: str) -> tuple[bool, str]:
    """Fetch and decode a text file from GitHub contents API."""
    response = requests.get(
        f"https://api.github.com/repos/{owner}/{repo_name}/contents/{path}",
        headers=github_headers(token),
        params={"ref": ref},
        timeout=25,
    )
    if response.status_code != 200:
        try:
            message = response.json().get("message", response.text)
        except ValueError:
            message = response.text
        return False, f"{path}: {message}"

    payload = response.json()
    if payload.get("encoding") != "base64":
        return False, f"{path}: unsupported encoding ({payload.get('encoding', 'unknown')})"

    try:
        decoded = base64.b64decode(payload.get("content", "")).decode("utf-8")
    except Exception:
        return False, f"{path}: file is not valid UTF-8 text"

    return True, decoded


def ask_cohere_for_repo_review(
    api_key: str,
    repo_full_name: str,
    branch: str,
    file_payload: list[dict[str, str]],
    user_focus: str,
) -> tuple[bool, str]:
    """Ask Cohere to produce actionable code review and improvement suggestions."""
    preamble = (
        "You are a senior code reviewer and software architect. "
        "Review the provided repository files and produce practical findings with severity. "
        "Focus on bugs, reliability, security, maintainability, and missing tests. "
        "Output in markdown with sections: Summary, Findings, Improvements, and Quick Wins. "
        "Each finding should include: severity (High/Medium/Low), file path, issue, and suggested fix."
    )

    bundle = {
        "repository": repo_full_name,
        "branch": branch,
        "focus": user_focus.strip() if user_focus.strip() else "General code quality and improvements",
        "files": file_payload,
    }

    ok, payload_or_error = call_cohere_chat(
        api_key=api_key,
        payload={
            "preamble": preamble,
            "message": json.dumps(bundle),
            "temperature": 0.2,
        },
        timeout=90,
    )
    if not ok:
        return False, payload_or_error

    return True, payload_or_error.get("text", "No response returned.")


def ask_cohere_for_patch_bundle_from_review(
    api_key: str,
    repo_full_name: str,
    branch: str,
    review_report: str,
    file_payload: list[dict[str, str]],
) -> tuple[bool, str, dict | None]:
    """Convert review suggestions into a patch-ready file bundle."""
    preamble = (
        "You are an expert software maintainer. "
        "Use the provided review findings and current files to produce an updated file bundle. "
        "Return only valid JSON with this exact shape: "
        "{\"summary\": string, \"files\": [{\"path\": string, \"content\": string}], \"notes\": [string]}. "
        "Do not include markdown fences or extra text. "
        "Only include files that need changes."
    )

    message_payload = {
        "repository": repo_full_name,
        "branch": branch,
        "instructions": "Apply the review recommendations and return a patch-ready updated file bundle.",
        "review_report": review_report,
        "current_files": file_payload,
    }

    ok, payload_or_error = call_cohere_chat(
        api_key=api_key,
        payload={
            "preamble": preamble,
            "message": json.dumps(message_payload),
            "temperature": 0.1,
        },
        timeout=90,
    )
    if not ok:
        return False, payload_or_error, None

    output_text = payload_or_error.get("text", "")
    parsed = extract_json_object(output_text)
    if not parsed:
        strict_message = (
            "Rewrite the following into VALID JSON only with this shape: "
            "{\"summary\": string, \"files\": [{\"path\": string, \"content\": string}], \"notes\": [string]}. "
            "Do not include markdown fences or explanations.\n\n"
            f"Content to convert:\n{output_text}"
        )
        retry_ok, retry_payload_or_error = call_cohere_chat(
            api_key=api_key,
            payload={
                "preamble": "You are a strict JSON formatter.",
                "message": strict_message,
                "temperature": 0.0,
            },
            timeout=45,
        )
        if not retry_ok:
            return False, retry_payload_or_error, None

        repaired_text = retry_payload_or_error.get("text", "")
        parsed = extract_json_object(repaired_text)
        if not parsed:
            return False, "Patch bundle output was not valid JSON after retry.", None

    return True, "", parsed


def seed_repo_template(
    token: str,
    owner: str,
    repo_name: str,
    template_name: str,
) -> tuple[bool, str]:
    """Populate a newly created repo with starter files."""
    if template_name == "Blank repo":
        return True, ""

    if template_name != "OpenWeather Streamlit app":
        return False, "Unknown template selected"

    file_map = build_openweather_template(repo_name)

    for path, content in file_map.items():
        status_code, result = upsert_repo_file(
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


tab_repo, tab_ai, tab_review, tab_patch = st.tabs([
    "📁 Repo Builder",
    "🤖 AI Assistant",
    "🔎 Repo Review",
    "🧩 Patch Bundle",
])

with tab_repo:
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
            if repo_name != repo_display_name.strip():
                st.info(f"Name adjusted to valid slug: **{repo_name}**")

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

with tab_ai:
    st.divider()
    st.subheader("🤖 AI Assistant for Streamlit")
    st.caption("Use Cohere to plan features, generate code, debug apps, and optionally write generated files to GitHub.")

    api_key = get_cohere_api_key()
    if not api_key:
        st.warning("COHERE_API_KEY not found in Streamlit secrets.")
        with st.form("cohere_key_form"):
            temp_key = st.text_input("Temporary Cohere API key", type="password")
            save_key = st.form_submit_button("Use this key for this session")
        if save_key and temp_key.strip():
            st.session_state["cohere_api_key"] = temp_key.strip()
            st.rerun()
        st.info("Add `COHERE_API_KEY` in `.streamlit/secrets.toml` for persistent local use.")
    else:
        with st.expander("Model settings", expanded=False):
            st.caption(f"Active model: {get_cohere_model()}")
            preset_options = [
                "command-a-03-2025",
                "command-r-08-2024",
                "custom",
            ]
            preset_model = st.selectbox(
                "Preset model",
                preset_options,
                index=0,
                key="cohere_model_preset",
                help="Pick a preset model or choose custom to enter a model name manually.",
            )
            model_input = st.text_input(
                "Override model for this session",
                value=st.session_state.get("cohere_model_override", ""),
                placeholder="Example: command-a-03-2025",
                help="Leave empty to use COHERE_MODEL from secrets or the default model.",
                disabled=(preset_model != "custom"),
            )
            model_col1, model_col2, model_col3 = st.columns(3)
            with model_col1:
                if st.button("Apply preset"):
                    if preset_model == "custom":
                        st.error("Choose a preset model or use Apply custom.")
                    else:
                        st.session_state["cohere_model_override"] = preset_model
                        st.rerun()
            with model_col2:
                if st.button("Apply model override"):
                    if model_input.strip():
                        st.session_state["cohere_model_override"] = model_input.strip()
                        st.rerun()
                    else:
                        st.error("Enter a model name before applying override.")
            with model_col3:
                if st.button("Use secrets/default"):
                    st.session_state.pop("cohere_model_override", None)
                    st.rerun()

        mode = st.radio(
            "Assistant mode",
            ["Chat help", "Generate file bundle"],
            horizontal=True,
            key="ai_assistant_mode",
        )

        if mode == "Chat help":
            st.info("Chat help is guidance-only. To write files to GitHub, use Generate file bundle mode.")
        else:
            st.info("Generate file bundle mode can preview, validate, and push selected files to a repo like test2.")

        if "ai_generated_bundle" not in st.session_state:
            st.session_state["ai_generated_bundle"] = None

        if "ai_assistant_messages" not in st.session_state:
            st.session_state["ai_assistant_messages"] = []

        if mode == "Chat help":
            if st.button("Clear assistant chat"):
                st.session_state["ai_assistant_messages"] = []
                st.rerun()

            for item in st.session_state["ai_assistant_messages"]:
                role = "assistant" if item["role"] == "CHATBOT" else "user"
                with st.chat_message(role):
                    st.markdown(item["message"])

            prompt = st.chat_input(
                "Ask for Streamlit help, e.g. 'Generate a multipage app with auth and charts'",
                key="cohere_assistant_input",
            )
            if prompt:
                st.session_state["ai_assistant_messages"].append({"role": "USER", "message": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                history = st.session_state["ai_assistant_messages"][:-1]
                cohere_history = [
                    {"role": item["role"], "message": item["message"]}
                    for item in history
                    if item["role"] in ("USER", "CHATBOT")
                ]

                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        ok, response_text = ask_cohere_for_streamlit_help(api_key, prompt, cohere_history)
                    if not ok:
                        st.error(response_text)
                        st.session_state["ai_assistant_messages"].append({
                            "role": "CHATBOT",
                            "message": f"Error: {response_text}",
                        })
                    else:
                        st.markdown(response_text)
                        st.session_state["ai_assistant_messages"].append({
                            "role": "CHATBOT",
                            "message": response_text,
                        })
        else:
            st.markdown("### Build App From Prompt")
            bundle_prompt = st.text_area(
                "Describe the app to generate",
                placeholder="Example: Build a Streamlit sales dashboard with CSV upload, KPI cards, filters, and line/bar charts.",
                height=120,
                key="bundle_prompt",
            )
            bundle_context = st.text_area(
                "Optional constraints or context",
                placeholder="Example: Use Plotly, include requirements.txt, and add a README with run steps.",
                height=100,
                key="bundle_context",
            )

            if st.button("Generate files with Cohere", type="primary"):
                if not bundle_prompt.strip():
                    st.error("Please describe the app you want to generate.")
                else:
                    with st.spinner("Generating structured files..."):
                        ok, error_msg, bundle = ask_cohere_for_file_bundle(api_key, bundle_prompt, bundle_context)

                    if not ok or not bundle:
                        st.error(error_msg)
                    else:
                        validation_errors = validate_generated_bundle(bundle)
                        st.session_state["ai_generated_bundle"] = {
                            "bundle": bundle,
                            "validation_errors": validation_errors,
                        }

            generated_state = st.session_state.get("ai_generated_bundle")
            if generated_state:
                bundle = generated_state["bundle"]
                validation_errors = generated_state["validation_errors"]

                st.markdown("### Generated Bundle Preview")
                summary = bundle.get("summary", "")
                if summary:
                    st.markdown(summary)

                if validation_errors:
                    st.error("Validation failed. Review the issues before pushing:")
                    for issue in validation_errors:
                        st.write(f"- {issue}")
                else:
                    st.success("Validation passed. Files are ready to push.")

                files = bundle.get("files", [])
                selection_key = "ai_bundle_selected_paths"
                current_paths = [item.get("path", "") for item in files if item.get("path")]
                existing_selection = st.session_state.get(selection_key)

                # Keep selections in sync with the currently generated bundle.
                if not isinstance(existing_selection, list) or set(existing_selection) != set(current_paths):
                    st.session_state[selection_key] = current_paths.copy()

                st.markdown("### Select Files To Push")
                select_col1, select_col2 = st.columns(2)
                with select_col1:
                    if st.button("Select all files"):
                        st.session_state[selection_key] = current_paths.copy()
                with select_col2:
                    if st.button("Clear selection"):
                        st.session_state[selection_key] = []

                selected_paths = st.multiselect(
                    "Choose files",
                    options=current_paths,
                    default=st.session_state.get(selection_key, current_paths.copy()),
                    key="ai_bundle_selected_paths_widget",
                    help="Only selected files will be committed to GitHub.",
                )
                st.session_state[selection_key] = selected_paths

                st.caption(f"Selected {len(selected_paths)} of {len(current_paths)} generated files")

                for file_item in files:
                    path = file_item.get("path", "")
                    content = file_item.get("content", "")
                    with st.expander(f"Preview: {path}", expanded=False):
                        st.code(content, language="python" if path.endswith(".py") else None)

                st.markdown("### Push To GitHub")
                default_repo = st.session_state.get("last_created_repo", {}).get("name", "")
                target_repo_name = st.text_input(
                    "Target repository name (under your GitHub account)",
                    value=default_repo,
                    key="bundle_target_repo",
                )
                commit_message = st.text_input(
                    "Commit message",
                    value="Add AI-generated app files",
                    key="bundle_commit_message",
                )

                if st.button("Approve and push files", type="secondary"):
                    if validation_errors:
                        st.error("Cannot push while validation errors exist.")
                    elif not selected_paths:
                        st.error("Please select at least one file to push.")
                    elif not target_repo_name.strip():
                        st.error("Please enter a target repository name.")
                    elif not repo_exists(token, user["login"], target_repo_name.strip()):
                        st.error("Target repository was not found under your account.")
                    else:
                        failed_paths: list[str] = []
                        pushed_count = 0
                        with st.spinner("Pushing generated files to GitHub..."):
                            for file_item in files:
                                path = file_item.get("path", "")
                                content = file_item.get("content", "")
                                if path not in selected_paths:
                                    continue
                                status_code, result = upsert_repo_file(
                                    token=token,
                                    owner=user["login"],
                                    repo_name=target_repo_name.strip(),
                                    path=path,
                                    content=content,
                                    message=commit_message.strip() or "Add AI-generated app files",
                                )
                                if status_code not in (200, 201):
                                    failed_paths.append(f"{path}: {result.get('message', 'unknown error')}")
                                else:
                                    pushed_count += 1

                        if failed_paths:
                            st.error("Some files failed to push:")
                            for item in failed_paths:
                                st.write(f"- {item}")
                        else:
                            st.success(f"Pushed {pushed_count} selected files successfully.")
                            github_repo_url = f"https://github.com/{user['login']}/{target_repo_name.strip()}"
                            st.markdown(f"🔗 {github_repo_url}")
                            render_post_push_deploy_controls(
                                owner=user["login"],
                                repo_name=target_repo_name.strip(),
                                selected_paths=selected_paths,
                                branch_key="ai_post_push_deploy_branch",
                                app_file_key="ai_post_push_deploy_app_file",
                            )

with tab_review:
    st.divider()
    st.subheader("🔎 Repo Review and Improvement Suggestions")
    st.caption("Select a GitHub repository, choose files, and get code review findings with improvement suggestions.")

    review_api_key = get_cohere_api_key()
    if not review_api_key:
        st.warning("COHERE_API_KEY is required for AI review in this tab.")
    else:
        repos_key = "review_repo_cache"
        if repos_key not in st.session_state:
            st.session_state[repos_key] = []
        if "review_last_report" not in st.session_state:
            st.session_state["review_last_report"] = ""
        if "review_last_file_payload" not in st.session_state:
            st.session_state["review_last_file_payload"] = []
        if "review_last_context" not in st.session_state:
            st.session_state["review_last_context"] = {}
        if "review_patch_bundle_state" not in st.session_state:
            st.session_state["review_patch_bundle_state"] = None

        col_refresh, col_hint = st.columns([1, 2])
        with col_refresh:
            if st.button("Refresh repo list", key="review_refresh_repos"):
                with st.spinner("Loading repositories from GitHub..."):
                    status_code, repos_data = list_user_repos(token)
                if status_code == 200 and isinstance(repos_data, list):
                    st.session_state[repos_key] = repos_data
                else:
                    message = repos_data.get("message", "Unknown error") if isinstance(repos_data, dict) else "Unknown error"
                    st.error(f"Unable to load repositories: {message}")
        with col_hint:
            st.caption("Includes repos you own or can access through collaborations/organizations.")

        if not st.session_state[repos_key]:
            with st.spinner("Loading repositories from GitHub..."):
                status_code, repos_data = list_user_repos(token)
            if status_code == 200 and isinstance(repos_data, list):
                st.session_state[repos_key] = repos_data
            else:
                message = repos_data.get("message", "Unknown error") if isinstance(repos_data, dict) else "Unknown error"
                st.error(f"Unable to load repositories: {message}")

        repos = st.session_state.get(repos_key, [])
        if repos:
            repo_label_map = {
                f"{item['full_name']} ({'private' if item.get('private') else 'public'})": item
                for item in repos
                if isinstance(item, dict) and item.get("full_name")
            }
            repo_choice = st.selectbox(
                "Repository",
                options=list(repo_label_map.keys()),
                key="review_repo_choice",
            )
            chosen_repo = repo_label_map[repo_choice]
            owner = chosen_repo["owner"]["login"]
            repo_name = chosen_repo["name"]
            default_branch = chosen_repo.get("default_branch", "main")

            branches_cache_key = f"review_branches_{owner}_{repo_name}"
            if branches_cache_key not in st.session_state:
                status_code, branches_data = list_repo_branches(token, owner, repo_name)
                if status_code == 200 and isinstance(branches_data, list):
                    st.session_state[branches_cache_key] = [b.get("name") for b in branches_data if b.get("name")]
                else:
                    st.session_state[branches_cache_key] = [default_branch]

            branch_options = st.session_state.get(branches_cache_key, [default_branch])
            selected_branch = st.selectbox(
                "Branch",
                options=branch_options,
                index=branch_options.index(default_branch) if default_branch in branch_options else 0,
                key="review_branch_choice",
            )

            files_cache_key = f"review_files_{owner}_{repo_name}_{selected_branch}"
            file_col1, file_col2 = st.columns([1, 1])
            with file_col1:
                if st.button("Load files", key="review_load_files"):
                    with st.spinner("Loading file list..."):
                        status_code, files_data = list_repo_files(token, owner, repo_name, selected_branch)
                    if status_code == 200 and isinstance(files_data, list):
                        st.session_state[files_cache_key] = files_data
                    else:
                        message = files_data.get("message", "Unknown error") if isinstance(files_data, dict) else "Unknown error"
                        st.error(f"Unable to load files: {message}")

            with file_col2:
                st.caption("Tip: select smaller sets of files for faster and better review quality.")

            if files_cache_key not in st.session_state:
                with st.spinner("Loading file list..."):
                    status_code, files_data = list_repo_files(token, owner, repo_name, selected_branch)
                if status_code == 200 and isinstance(files_data, list):
                    st.session_state[files_cache_key] = files_data
                else:
                    st.session_state[files_cache_key] = []

            repo_files = st.session_state.get(files_cache_key, [])
            if repo_files:
                text_like_files = [
                    item for item in repo_files
                    if isinstance(item, dict)
                    and item.get("path")
                    and not item.get("path", "").lower().endswith(
                        (".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".exe", ".woff", ".woff2")
                    )
                ]
                all_paths = [item["path"] for item in text_like_files]
                suggested_defaults = all_paths[: min(8, len(all_paths))]

                selected_paths = st.multiselect(
                    "Files to review",
                    options=all_paths,
                    default=suggested_defaults,
                    key="review_selected_files",
                )

                focus_area = st.text_input(
                    "Review focus (optional)",
                    placeholder="Example: reliability, input validation, and maintainability",
                    key="review_focus",
                )
                max_chars_per_file = st.slider(
                    "Max characters per file",
                    min_value=2000,
                    max_value=30000,
                    value=12000,
                    step=1000,
                    key="review_max_chars",
                    help="Long files are truncated to keep review responses fast and useful.",
                )

                if st.button("Run AI code review", type="primary", key="review_run_button"):
                    if not selected_paths:
                        st.error("Select at least one file to review.")
                    else:
                        file_payload: list[dict[str, str]] = []
                        skipped: list[str] = []
                        with st.spinner("Fetching files from GitHub..."):
                            for path in selected_paths:
                                ok, content_or_error = get_repo_file_content(
                                    token=token,
                                    owner=owner,
                                    repo_name=repo_name,
                                    path=path,
                                    ref=selected_branch,
                                )
                                if not ok:
                                    skipped.append(content_or_error)
                                    continue

                                content = content_or_error
                                truncated = False
                                if len(content) > max_chars_per_file:
                                    content = content[:max_chars_per_file]
                                    truncated = True

                                file_payload.append(
                                    {
                                        "path": path,
                                        "content": content,
                                        "truncated": "yes" if truncated else "no",
                                    }
                                )

                        if not file_payload:
                            st.error("No readable text files were available for review.")
                            for item in skipped[:20]:
                                st.write(f"- {item}")
                        else:
                            with st.spinner("Analyzing code with Cohere..."):
                                ok, review_text = ask_cohere_for_repo_review(
                                    api_key=review_api_key,
                                    repo_full_name=f"{owner}/{repo_name}",
                                    branch=selected_branch,
                                    file_payload=file_payload,
                                    user_focus=focus_area,
                                )

                            if not ok:
                                st.error(review_text)
                            else:
                                st.session_state["review_last_report"] = review_text
                                st.session_state["review_last_file_payload"] = file_payload
                                st.session_state["review_last_context"] = {
                                    "owner": owner,
                                    "repo_name": repo_name,
                                    "branch": selected_branch,
                                }
                                st.session_state["review_patch_bundle_state"] = None

                            if skipped:
                                st.warning("Some files were skipped:")
                                for item in skipped[:20]:
                                    st.write(f"- {item}")

                latest_report = st.session_state.get("review_last_report", "")
                latest_payload = st.session_state.get("review_last_file_payload", [])
                latest_context = st.session_state.get("review_last_context", {})

                if latest_report and latest_context.get("repo_name") == repo_name:
                    st.markdown("### Review Report")
                    st.markdown(latest_report)
                    st.info("Next step: open the 🧩 Patch Bundle tab to convert this review into a patch-ready bundle and push/re-push changes.")
            else:
                st.info("No files found for this repository and branch.")

with tab_patch:
    st.divider()
    st.subheader("🧩 Patch Bundle and Re-Push")
    st.caption("Convert the latest review report into a patch-ready bundle, preview changes, and push/re-push to GitHub.")

    patch_api_key = get_cohere_api_key()
    if not patch_api_key:
        st.warning("COHERE_API_KEY is required for patch bundle generation.")
    else:
        latest_report = st.session_state.get("review_last_report", "")
        latest_payload = st.session_state.get("review_last_file_payload", [])
        latest_context = st.session_state.get("review_last_context", {})

        if not latest_report or not latest_payload or not latest_context:
            st.info("No review data found yet. Run a code review first in the 🔎 Repo Review tab.")
        else:
            active_owner = latest_context.get("owner", "")
            active_repo = latest_context.get("repo_name", "")
            active_branch = latest_context.get("branch", "main")
            st.caption(f"Using latest review context: {active_owner}/{active_repo} ({active_branch})")

            if st.button("Convert suggestions to patch-ready bundle", key="patch_convert_bundle"):
                with st.spinner("Generating patch-ready file bundle..."):
                    ok, error_msg, patch_bundle = ask_cohere_for_patch_bundle_from_review(
                        api_key=patch_api_key,
                        repo_full_name=f"{active_owner}/{active_repo}",
                        branch=active_branch,
                        review_report=latest_report,
                        file_payload=latest_payload,
                    )

                if not ok or not patch_bundle:
                    st.error(error_msg)
                else:
                    validation_errors = validate_generated_bundle(patch_bundle)
                    st.session_state["review_patch_bundle_state"] = {
                        "bundle": patch_bundle,
                        "validation_errors": validation_errors,
                        "repo_name": active_repo,
                    }

            patch_state = st.session_state.get("review_patch_bundle_state")
            if patch_state and patch_state.get("repo_name") == active_repo:
                patch_bundle = patch_state["bundle"]
                patch_errors = patch_state["validation_errors"]

                st.markdown("### Patch-Ready Bundle")
                patch_summary = patch_bundle.get("summary", "")
                if patch_summary:
                    st.markdown(patch_summary)

                if patch_errors:
                    st.error("Patch bundle validation failed:")
                    for item in patch_errors:
                        st.write(f"- {item}")
                else:
                    st.success("Patch bundle validation passed.")

                patch_files = patch_bundle.get("files", [])
                patch_paths = [item.get("path", "") for item in patch_files if item.get("path")]
                patch_selection_key = "review_patch_selected_paths"
                saved_patch_selection = st.session_state.get(patch_selection_key)
                if not isinstance(saved_patch_selection, list) or set(saved_patch_selection) != set(patch_paths):
                    st.session_state[patch_selection_key] = patch_paths.copy()

                patch_selected_paths = st.multiselect(
                    "Patch files to push",
                    options=patch_paths,
                    default=st.session_state.get(patch_selection_key, patch_paths.copy()),
                    key="review_patch_selected_paths_widget",
                )
                st.session_state[patch_selection_key] = patch_selected_paths

                for file_item in patch_files:
                    path = file_item.get("path", "")
                    content = file_item.get("content", "")
                    with st.expander(f"Patch preview: {path}", expanded=False):
                        st.code(content, language="python" if path.endswith(".py") else None)

                st.markdown("### Push or Re-Push Patch Bundle")
                patch_target_repo = st.text_input(
                    "Target repository name",
                    value=active_repo,
                    key="review_patch_target_repo",
                )
                patch_commit_message = st.text_input(
                    "Commit message",
                    value="Apply AI review improvements",
                    key="review_patch_commit_message",
                )

                push_col1, push_col2 = st.columns(2)
                with push_col1:
                    push_clicked = st.button("Push patch bundle", key="review_push_patch")
                with push_col2:
                    repush_clicked = st.button("Re-push last patch", key="review_repush_patch")

                if push_clicked or repush_clicked:
                    if patch_errors:
                        st.error("Cannot push while validation errors exist.")
                    elif not patch_selected_paths:
                        st.error("Select at least one patch file to push.")
                    elif not patch_target_repo.strip():
                        st.error("Please enter a target repository name.")
                    elif not repo_exists(token, user["login"], patch_target_repo.strip()):
                        st.error("Target repository was not found under your account.")
                    else:
                        failed_paths: list[str] = []
                        pushed_count = 0
                        with st.spinner("Pushing patch bundle to GitHub..."):
                            for file_item in patch_files:
                                path = file_item.get("path", "")
                                content = file_item.get("content", "")
                                if path not in patch_selected_paths:
                                    continue
                                status_code, result = upsert_repo_file(
                                    token=token,
                                    owner=user["login"],
                                    repo_name=patch_target_repo.strip(),
                                    path=path,
                                    content=content,
                                    message=patch_commit_message.strip() or "Apply AI review improvements",
                                )
                                if status_code not in (200, 201):
                                    failed_paths.append(f"{path}: {result.get('message', 'unknown error')}")
                                else:
                                    pushed_count += 1

                        if failed_paths:
                            st.error("Some patch files failed to push:")
                            for item in failed_paths:
                                st.write(f"- {item}")
                        else:
                            action = "Re-pushed" if repush_clicked else "Pushed"
                            st.success(f"{action} {pushed_count} patch files successfully.")
                            github_repo_url = f"https://github.com/{user['login']}/{patch_target_repo.strip()}"
                            st.markdown(f"🔗 {github_repo_url}")
                            render_post_push_deploy_controls(
                                owner=user["login"],
                                repo_name=patch_target_repo.strip(),
                                selected_paths=patch_selected_paths,
                                branch_key="patch_post_push_deploy_branch",
                                app_file_key="patch_post_push_deploy_app_file",
                            )

