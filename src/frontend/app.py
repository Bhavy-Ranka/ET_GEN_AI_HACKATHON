import os
import streamlit as st
import requests

BASE_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="AI-Smart City", layout="wide")

st.markdown("""
<style>
    .auth-card {
        background: linear-gradient(135deg, #0d1b2a 0%, #1a3a5c 100%);
        border: 1px solid #2e6da4;
        border-radius: 12px;
        padding: 32px 36px;
        max-width: 450px;
        margin: 40px auto 0 auto;
        box-shadow: 0 8px 32px rgba(0,0,0,0.4);
    }
    .auth-title {
        color: #d0e8ff;
        font-size: 26px;
        font-weight: 700;
        text-align: center;
        margin-bottom: 4px;
        letter-spacing: 1px;
    }
    .auth-subtitle {
        color: #7aafd4;
        font-size: 13px;
        text-align: center;
        margin-bottom: 24px;
    }
    .user-badge {
        background: #1a3a5c;
        border: 1px solid #2e6da4;
        border-radius: 20px;
        padding: 4px 14px;
        color: #d0e8ff;
        font-size: 13px;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "token" not in st.session_state:
    st.session_state["token"] = None
if "refresh_token" not in st.session_state:
    st.session_state["refresh_token"] = None
if "username" not in st.session_state:
    st.session_state["username"] = None
if "auth_mode" not in st.session_state:
    st.session_state["auth_mode"] = "Login"
if "login_step" not in st.session_state:
    st.session_state["login_step"] = 1
if "signup_step" not in st.session_state:
    st.session_state["signup_step"] = 1
if "pending_email" not in st.session_state:
    st.session_state["pending_email"] = None


def safe_json_response(resp):
    try:
        return resp.json()
    except Exception:
        return {"detail": f"Server returned error HTTP {resp.status_code}. Response: {resp.text[:150]}"}


def refresh_access_token():
    """Attempts to refresh access token using refresh_token."""
    refresh_tok = st.session_state.get("refresh_token")
    if not refresh_tok:
        return False
    try:
        resp = requests.post(f"{BASE_URL}/refresh", json={"refresh_token": refresh_tok})
        if resp.status_code == 200:
            data = safe_json_response(resp)
            st.session_state["token"] = data["access_token"]
            st.session_state["refresh_token"] = data["refresh_token"]
            return True
    except Exception:
        pass
    return False


def authenticated_request(method: str, url: str, **kwargs):
    """Sends authenticated request with auto-refresh mechanism for expired tokens."""
    headers = kwargs.get("headers", {})
    headers["Authorization"] = f"Bearer {st.session_state.get('token')}"
    kwargs["headers"] = headers

    response = requests.request(method, url, **kwargs)
    if response.status_code == 401:
        if refresh_access_token():
            headers["Authorization"] = f"Bearer {st.session_state.get('token')}"
            kwargs["headers"] = headers
            response = requests.request(method, url, **kwargs)
        else:
            st.session_state.clear()
            st.rerun()
    return response


def auth_page():
    st.markdown("<h1 style='text-align:center;color:#d0e8ff;letter-spacing:2px;margin-top:20px;'>🏙️ AI SMART CITY</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:#7aafd4;margin-bottom:0;'>Intelligent Urban Complaint Management</p>", unsafe_allow_html=True)

    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        col1, col2 = st.columns(2)
        with col1:
            if st.button(" Login", use_container_width=True,
                         type="primary" if st.session_state["auth_mode"] == "Login" else "secondary"):
                st.session_state["auth_mode"] = "Login"
                st.session_state["login_step"] = 1
                st.rerun()
        with col2:
            if st.button("Sign Up", use_container_width=True,
                         type="primary" if st.session_state["auth_mode"] == "Sign Up" else "secondary"):
                st.session_state["auth_mode"] = "Sign Up"
                st.session_state["signup_step"] = 1
                st.rerun()

        st.markdown("---")

        if st.session_state["auth_mode"] == "Login":
            st.markdown("<div class='auth-title'>Welcome Back</div>", unsafe_allow_html=True)

            if st.session_state["login_step"] == 1:
                st.markdown("<div class='auth-subtitle'>Step 1: Enter your Email ID and Password</div>", unsafe_allow_html=True)

                email = st.text_input("Email ID", key="login_email", placeholder="user@example.com")
                password = st.text_input("Password", type="password", key="login_pass", placeholder="Enter password")

                if st.button("Send OTP →", use_container_width=True, type="primary"):
                    if not email.strip() or not password.strip():
                        st.warning("Please fill in both email and password.")
                    else:
                        try:
                            resp = requests.post(f"{BASE_URL}/login/request-otp", json={"email": email, "password": password})
                            data = safe_json_response(resp)
                            if resp.status_code == 200:
                                st.session_state["pending_email"] = email.strip().lower()
                                st.session_state["login_step"] = 2
                                st.success("OTP sent to your email inbox!")
                                st.rerun()
                            else:
                                detail = data.get("detail", "Failed to send OTP.")
                                st.error(f" {detail}")
                        except requests.exceptions.ConnectionError:
                            st.error("Cannot connect to backend. Is it running?")

            else:  # Step 2: OTP Verification
                st.markdown(f"<div class='auth-subtitle'>Step 2: Enter 6-digit OTP sent to <b>{st.session_state['pending_email']}</b></div>", unsafe_allow_html=True)

                otp_code = st.text_input("6-Digit Verification OTP", key="login_otp", placeholder="123456")

                if st.button("Verify OTP & Login →", use_container_width=True, type="primary"):
                    if not otp_code.strip():
                        st.warning("Please enter the 6-digit OTP code.")
                    else:
                        try:
                            payload = {"email": st.session_state["pending_email"], "otp": otp_code.strip()}
                            resp = requests.post(f"{BASE_URL}/login/verify-otp", json=payload)
                            data = safe_json_response(resp)
                            if resp.status_code == 200:
                                st.session_state["logged_in"] = True
                                st.session_state["token"] = data["access_token"]
                                st.session_state["refresh_token"] = data["refresh_token"]
                                st.session_state["username"] = data["user"]["email"]
                                st.session_state["login_step"] = 1
                                st.success(f"Welcome back, **{data['user']['email']}**! ")
                                st.rerun()
                            else:
                                detail = data.get("detail", "OTP verification failed.")
                                st.error(f" {detail}")
                        except requests.exceptions.ConnectionError:
                            st.error("Cannot connect to backend. Is it running?")

                if st.button("← Back / Change Email", use_container_width=True, type="secondary"):
                    st.session_state["login_step"] = 1
                    st.rerun()

        else:  # Sign Up Mode
            st.markdown("<div class='auth-title'>Create Account</div>", unsafe_allow_html=True)

            if st.session_state["signup_step"] == 1:
                st.markdown("<div class='auth-subtitle'>Step 1: Enter Email & Choose Password</div>", unsafe_allow_html=True)

                new_email = st.text_input("Email ID", key="signup_email", placeholder="user@example.com")
                new_pass = st.text_input("Choose Password", type="password", key="signup_pass", placeholder="Min 6 characters")
                confirm_pass = st.text_input("Confirm Password", type="password", key="signup_confirm", placeholder="Re-enter password")

                if st.button("Send Verification OTP →", use_container_width=True, type="primary"):
                    if not new_email.strip() or not new_pass.strip():
                        st.warning("Please fill in all fields.")
                    elif "@" not in new_email:
                        st.warning("Please enter a valid email address.")
                    elif len(new_pass) < 6:
                        st.warning("Password must be at least 6 characters.")
                    elif new_pass != confirm_pass:
                        st.error("Passwords do not match.")
                    else:
                        try:
                            resp = requests.post(f"{BASE_URL}/signup/request-otp", json={"email": new_email, "password": new_pass})
                            data = safe_json_response(resp)
                            if resp.status_code == 200:
                                st.session_state["pending_email"] = new_email.strip().lower()
                                st.session_state["signup_step"] = 2
                                st.success("OTP sent to your email inbox!")
                                st.rerun()
                            else:
                                detail = data.get("detail", "Sign up OTP request failed.")
                                st.error(f" {detail}")
                        except requests.exceptions.ConnectionError:
                            st.error("Cannot connect to backend. Is it running?")

            else:  # Step 2: OTP Verification
                st.markdown(f"<div class='auth-subtitle'>Step 2: Enter 6-digit OTP sent to <b>{st.session_state['pending_email']}</b></div>", unsafe_allow_html=True)

                otp_code = st.text_input("6-Digit Verification OTP", key="signup_otp", placeholder="123456")



                if st.button("Verify OTP & Create Account →", use_container_width=True, type="primary"):
                    if not otp_code.strip():
                        st.warning("Please enter the 6-digit OTP code.")
                    else:
                        try:
                            payload = {"email": st.session_state["pending_email"], "otp": otp_code.strip()}
                            resp = requests.post(f"{BASE_URL}/signup/verify-otp", json=payload)
                            data = safe_json_response(resp)
                            if resp.status_code == 200:
                                st.session_state["logged_in"] = True
                                st.session_state["token"] = data["access_token"]
                                st.session_state["refresh_token"] = data["refresh_token"]
                                st.session_state["username"] = data["user"]["email"]
                                st.session_state["signup_step"] = 1
                                st.success("Account created successfully! ")
                                st.rerun()
                            else:
                                detail = data.get("detail", "Sign up verification failed.")
                                st.error(f" {detail}")
                        except requests.exceptions.ConnectionError:
                            st.error("Cannot connect to backend. Is it running?")

                if st.button("← Back / Change Details", use_container_width=True, type="secondary"):
                    st.session_state["signup_step"] = 1
                    st.rerun()



def main_app():
    col_title, col_user = st.columns([5, 1])
    with col_title:
        st.title("AI SMART CITY")
    with col_user:
        st.markdown(f"<div class='user-badge'>{st.session_state['username']}</div>", unsafe_allow_html=True)
        if st.button("Logout", type="secondary"):
            st.session_state.clear()
            st.rerun()

    # ─── 1. Upload Section ───
    st.header("Upload Image")
    uploaded_file = st.file_uploader("Choose a file", type=['png', 'jpg', 'jpeg'])

    if uploaded_file is not None:
        if st.button("Upload to Server"):
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
            try:
                response = authenticated_request("POST", f"{BASE_URL}/uploadfile/", files=files)
                if response.status_code == 200:
                    st.session_state["uploaded_filename"] = uploaded_file.name
                    st.session_state["uploaded_image"] = uploaded_file.getvalue()
                    st.success(f"File '{uploaded_file.name}' saved successfully.")
                else:
                    st.error(f"Upload failed with status: {response.status_code}")
            except requests.exceptions.ConnectionError:
                st.error("Could not connect to the Backend. Is it running?")

    st.divider()

    st.header("Enter User Description")
    description_input = st.text_area("Enter your description:", placeholder="What is in this image?")
    address_input = st.text_input("Enter the address", placeholder="Address of the complaint area")

    if st.button("Upload Description"):
        if not description_input.strip():
            st.warning("Please enter a description")
        elif not address_input.strip():
            st.warning("Please enter an address")
        elif "uploaded_filename" not in st.session_state:
            st.warning("Please upload an image first")
        else:
            payload = {
                "text": description_input,
                "address": address_input,
                "filename": st.session_state["uploaded_filename"]
            }
            try:
                response = authenticated_request("POST", f"{BASE_URL}/imageDescription", json=payload)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("pipeline_warning"):
                        st.warning(data["pipeline_warning"])
                    st.session_state["confirmed_description"] = data.get("description")
                    st.session_state["confirmed_address"] = data.get("address") or address_input
                    st.session_state["pipeline"] = data.get("pipeline", {})
                    st.success("Description uploaded successfully.")
                else:
                    st.error(f"Failed to upload description. Status: {response.status_code}")
            except requests.exceptions.ConnectionError:
                st.error("Could not connect to the Backend.")

    st.divider()

    if "uploaded_image" in st.session_state and "confirmed_description" in st.session_state:
        st.header("Result")
        pipeline = st.session_state.get("pipeline", {})
        severity = pipeline.get("severity", "N/A")
        severity_color = {"High": "#ff4b4b", "Medium": "#ffa500", "Low": "#00c853"}.get(severity, "#7aafd4")

        col_img, col_info = st.columns([1, 1])

        with col_img:
            st.image(st.session_state["uploaded_image"], use_container_width=True)

        with col_info:
            st.markdown(f"""
            <div style='background:#0d1b2a;border:1px solid #2e6da4;border-radius:12px;padding:20px;height:100%;'>
                <h4 style='color:#d0e8ff;margin-top:0;'>{pipeline.get("issue_title", "Civic Issue")}</h4>
                <hr style='border-color:#2e6da4;'/>
                <p style='color:#7aafd4;margin:6px 0;'><b style='color:#d0e8ff;'> Description:</b><br>{st.session_state["confirmed_description"]}</p>
                <p style='color:#7aafd4;margin:6px 0;'><b style='color:#d0e8ff;'> Address:</b> {st.session_state.get("confirmed_address", "N/A")}</p>
                <p style='color:#7aafd4;margin:6px 0;'><b style='color:#d0e8ff;'> Category:</b> {pipeline.get("category", "N/A")}</p>
                <p style='margin:6px 0;'><b style='color:#d0e8ff;'> Severity:</b> 
                    <span style='background:{severity_color};color:#fff;padding:2px 10px;border-radius:12px;font-weight:bold;'>{severity}</span>
                </p>
                <p style='color:#7aafd4;margin:6px 0;'><b style='color:#d0e8ff;'> AI Summary:</b><br>{pipeline.get("detailed_description", "N/A")}</p>
                <p style='color:#7aafd4;margin:6px 0;'><b style='color:#d0e8ff;'> Tags:</b> {", ".join(pipeline.get("tags", [])) or "N/A"}</p>
            </div>
            """, unsafe_allow_html=True)


def admin_panel():
    col_title, col_user = st.columns([5, 1])
    with col_title:
        st.title("Admin Dashboard")
    with col_user:
        st.markdown(f"<div class='user-badge'>🛡️ {st.session_state['username']}</div>", unsafe_allow_html=True)
        if st.button("Logout", type="secondary"):
            st.session_state.clear()
            st.rerun()

    st.divider()

    try:
        resp = authenticated_request("GET", f"{BASE_URL}/admin/complaints")
        if resp.status_code == 200:
            all_complaints = resp.json()

            if not all_complaints:
                st.info("No active complaints.")
                return

            high_sev = [c for c in all_complaints if c.get('severity') == "High"]
            med_sev = [c for c in all_complaints if c.get('severity') == "Medium"]
            low_sev = [c for c in all_complaints if c.get('severity', 'Low') not in ["High", "Medium"]]

            col1, col2, col3 = st.columns(3)

            sections = [
                (col1, "🔴 High Severity", high_sev, "#ff4b4b"),
                (col2, "🟡 Medium Severity", med_sev, "#ffa500"),
                (col3, "🟢 Low Severity", low_sev, "#00c853")
            ]

            for column, title, data, color in sections:
                with column:
                    st.markdown(f"<h3 style='text-align:center; color:{color};'>{title}</h3>", unsafe_allow_html=True)
                    st.markdown(f"<div style='border-bottom: 2px solid {color}; margin-bottom:15px;'></div>", unsafe_allow_html=True)

                    if not data:
                        st.write(" Clear")

                    for c in data:
                        with st.container():
                            st.markdown(f"""
                            <div style='border: 1px solid {color}; border-radius: 10px; padding: 10px; margin-bottom: 10px; background-color: rgba(0,0,0,0.2);'>
                                <p style='margin:0; font-weight:bold;'>{c.get('issue_title', 'Untitled')}</p>
                                <p style='font-size: 0.8em; color: #7aafd4;'>📍 {c.get('formatted_location', 'Unknown')}</p>
                            </div>
                            """, unsafe_allow_html=True)

                            with st.expander("View Details"):
                                if c.get('image_path'):
                                    img_name = os.path.basename(c['image_path'].replace('\\', '/'))
                                    st.image(f"{BASE_URL}/view/{img_name}", use_container_width=True)
                                st.write(f"**Reported by:** {c.get('user_name')}")
                                st.write(f"**Description:** {c.get('detailed_description')}")

                                if st.button(f" Mark Resolved", key=f"btn_{c['_id']}"):
                                    del_resp = authenticated_request("DELETE", f"{BASE_URL}/admin/complaints/{c['_id']}")
                                    if del_resp.status_code == 200:
                                        st.success("Resolved!")
                                        st.rerun()
                                    else:
                                        st.error("Failed to delete.")

        else:
            st.error("Failed to fetch data from server.")
    except Exception as e:
        st.error(f"Error: {e}")


ADMIN_USERS = ["bhavyranka@gmail.com"]

if st.session_state["logged_in"]:
    if st.session_state["username"] in ADMIN_USERS:
        admin_panel()
    else:
        main_app()
else:
    auth_page()
