"""
Email Batch Generator - Generate Gmail batch links for sending emails to users.
Parse user IDs, configure email content, and generate CSVs with Gmail links.
"""
import streamlit as st
import os
import sys
import re
import io
import csv
import json
from urllib.parse import quote
from datetime import datetime
from dotenv import load_dotenv

# Setup paths 
current_dir = os.path.dirname(__file__)
scripts_dir = os.path.abspath(os.path.join(current_dir, '..'))
parent_dir = os.path.abspath(os.path.join(scripts_dir, '..'))
sys.path.insert(0, parent_dir)
sys.path.insert(0, scripts_dir)

try:
    from dependencies import get_supabase_client
except ImportError:
    st.error("Error: 'dependencies.py' not found.")
    st.stop()

# Load environment
dotenv_path = os.path.join(parent_dir, '.env')
load_dotenv(dotenv_path)

# --- Supabase Connection ---
try:
    supabase = get_supabase_client()
except Exception as e:
    st.error(f"Supabase connection failed: {e}")
    st.stop()

# Constants
MAX_URL_LENGTH = 1800
DEFAULT_BATCH_SIZE = 25
DEFAULT_TEST_EMAILS = """aryan@heywavelength.com
jayanth@heywavelength.com
vinit@heywavelength.com
ishaan@heywavelength.com
chetan@heywavelength.com"""

TEMPLATES_FILE = os.path.join(os.path.dirname(__file__), "email_templates.json")

# --- Template Functions ---

def load_templates() -> dict:
    """Load templates from JSON file."""
    if os.path.exists(TEMPLATES_FILE):
        with open(TEMPLATES_FILE, 'r') as f:
            return json.load(f)
    return {"default_template": None, "templates": {}}


def save_templates(data: dict):
    """Save templates to JSON file."""
    with open(TEMPLATES_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def get_template_names() -> list[str]:
    """Get list of template names."""
    data = load_templates()
    return list(data.get("templates", {}).keys())


def get_template(name: str) -> dict | None:
    """Get a specific template by name."""
    data = load_templates()
    return data.get("templates", {}).get(name)


def get_default_template() -> str | None:
    """Get the default template name."""
    data = load_templates()
    return data.get("default_template")


def set_default_template(name: str | None):
    """Set the default template."""
    data = load_templates()
    data["default_template"] = name
    save_templates(data)


def add_template(name: str, male_subject: str, male_content: str, female_subject: str, female_content: str):
    """Add a new template."""
    data = load_templates()
    data["templates"][name] = {
        "male": {"subject": male_subject, "content": male_content},
        "female": {"subject": female_subject, "content": female_content}
    }
    save_templates(data)


def delete_template(key: str):
    """Delete a template."""
    data = load_templates()
    if key in data.get("templates", {}):
        del data["templates"][key]
        if data.get("default_template") == key:
            data["default_template"] = None
        save_templates(data)


def rename_template(old_name: str, new_name: str):
    """Rename a template."""
    data = load_templates()
    if old_name in data.get("templates", {}):
        template = data["templates"].pop(old_name)
        data["templates"][new_name] = template
        if data.get("default_template") == old_name:
            data["default_template"] = new_name
        save_templates(data)


# --- Helper Functions ---

def parse_user_ids(input_text: str) -> tuple[list[str], list[dict]]:
    """
    Parse user IDs from various formats.
    Returns (valid_ids, errors)

    Supported formats:
    - List format: ["id1", "id2"]
    - Quoted comma separated: "id1", "id2", "id3"
    - Plain comma separated: id1, id2, id3
    - Newline separated
    - Mixed formats
    """
    errors = []
    valid_ids = []

    if not input_text.strip():
        return [], [{"position": 0, "message": "Input is empty", "context": ""}]

    text = input_text.strip()

    # Try to detect the format
    # Check if it looks like a JSON array
    if text.startswith('[') and text.endswith(']'):
        # JSON array format
        text = text[1:-1].strip()

    # Split by common delimiters
    # First, try to find quoted strings
    quoted_pattern = r'"([^"]*)"'
    quoted_matches = re.findall(quoted_pattern, text)

    if quoted_matches:
        # Found quoted strings, use them
        for match in quoted_matches:
            match = match.strip()
            if match:
                valid_ids.append(match)
    else:
        # No quotes found, try splitting by comma or newline
        # Replace newlines with commas for uniform processing
        text = text.replace('\n', ',')
        parts = text.split(',')

        for i, part in enumerate(parts):
            part = part.strip()
            # Remove any quotes that might be present
            part = part.strip('"\'')
            if part:
                valid_ids.append(part)

    # Validate each ID and check for common issues
    validated_ids = []
    for i, id_val in enumerate(valid_ids):
        # Check for UUID format (basic validation)
        uuid_pattern = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
        if re.match(uuid_pattern, id_val):
            validated_ids.append(id_val)
        else:
            # Find position in original text
            pos = input_text.find(id_val)
            line_num = input_text[:pos].count('\n') + 1 if pos >= 0 else 0

            # Check specific issues
            if ' ' in id_val:
                errors.append({
                    "position": i + 1,
                    "message": f"Contains spaces",
                    "context": f"'{id_val}' at line ~{line_num}",
                    "value": id_val
                })
            elif len(id_val) < 36:
                errors.append({
                    "position": i + 1,
                    "message": f"Too short (expected 36 chars, got {len(id_val)})",
                    "context": f"'{id_val}' at line ~{line_num}",
                    "value": id_val
                })
            elif len(id_val) > 36:
                errors.append({
                    "position": i + 1,
                    "message": f"Too long (expected 36 chars, got {len(id_val)})",
                    "context": f"'{id_val}' at line ~{line_num}",
                    "value": id_val
                })
            elif id_val.count('-') != 4:
                errors.append({
                    "position": i + 1,
                    "message": f"Invalid UUID format (expected 4 dashes, got {id_val.count('-')})",
                    "context": f"'{id_val}' at line ~{line_num}",
                    "value": id_val
                })
            else:
                errors.append({
                    "position": i + 1,
                    "message": f"Invalid UUID format",
                    "context": f"'{id_val}' at line ~{line_num}",
                    "value": id_val
                })

    return validated_ids, errors


def detect_syntax_errors(input_text: str) -> list[dict]:
    """Detect common syntax errors in the input."""
    errors = []

    # Check for unmatched quotes
    quote_count = input_text.count('"')
    if quote_count % 2 != 0:
        # Find position of issue
        in_quote = False
        for i, char in enumerate(input_text):
            if char == '"':
                in_quote = not in_quote
        if in_quote:
            # Find the last quote
            last_quote_pos = input_text.rfind('"')
            line_num = input_text[:last_quote_pos].count('\n') + 1
            errors.append({
                "type": "syntax",
                "message": f"Unmatched quote - odd number of quotes ({quote_count})",
                "position": last_quote_pos,
                "line": line_num
            })

    # Check for missing commas between quoted strings
    pattern = r'"[^"]*"\s*"'
    matches = list(re.finditer(pattern, input_text))
    for match in matches:
        pos = match.start()
        line_num = input_text[:pos].count('\n') + 1
        errors.append({
            "type": "syntax",
            "message": "Missing comma between quoted strings",
            "position": pos,
            "line": line_num,
            "context": match.group()[:50]
        })

    # Check for double commas
    double_comma_pattern = r',\s*,'
    matches = list(re.finditer(double_comma_pattern, input_text))
    for match in matches:
        pos = match.start()
        line_num = input_text[:pos].count('\n') + 1
        errors.append({
            "type": "syntax",
            "message": "Double comma found (empty value)",
            "position": pos,
            "line": line_num
        })

    # Check for trailing comma before closing bracket
    if input_text.strip().startswith('['):
        trailing_comma = re.search(r',\s*\]', input_text)
        if trailing_comma:
            pos = trailing_comma.start()
            line_num = input_text[:pos].count('\n') + 1
            errors.append({
                "type": "syntax",
                "message": "Trailing comma before closing bracket",
                "position": pos,
                "line": line_num
            })

    return errors


def generate_gmail_url(emails: list[str], subject: str, body: str, email_field: str = "bcc") -> str:
    """Generate a Gmail compose URL.

    Args:
        emails: List of email addresses
        subject: Email subject
        body: Email body
        email_field: Where to put emails - "to", "cc", or "bcc" (default)
    """
    encoded_subject = quote(subject)
    encoded_body = quote(body)
    emails_str = ",".join(emails)

    url = f"https://mail.google.com/mail/u/0/?fs=1&{email_field}={emails_str}&su={encoded_subject}&body={encoded_body}&tf=cm"

    return url


def batch_emails(emails: list[str], subject: str, body: str, max_batch_size: int = DEFAULT_BATCH_SIZE) -> list[list[str]]:
    """Split emails into batches that fit within URL limits."""
    batches = []
    current_batch = []

    for email in emails:
        current_batch.append(email)

        # Check if URL would be too long
        test_url = generate_gmail_url(current_batch, subject, body)
        if len(test_url) > MAX_URL_LENGTH or len(current_batch) >= max_batch_size:
            if len(test_url) > MAX_URL_LENGTH:
                current_batch.pop()
                if current_batch:
                    batches.append(current_batch.copy())
                current_batch = [email]
            else:
                batches.append(current_batch.copy())
                current_batch = []

    if current_batch:
        batches.append(current_batch)

    return batches


def generate_csv_content(batches: list[list[str]], users: list[dict], subject: str, body: str, test_emails: list[str], gender: str, email_field: str = "bcc") -> str:
    """Generate CSV content for download."""
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)

    # Header
    writer.writerow(["batch_number", "email_count", "isTestBatch", "user_ids", "emails", "gmail_link"])

    # Test batch first (batch 0)
    test_gmail_link = generate_gmail_url(test_emails, subject, body, email_field)
    writer.writerow([0, len(test_emails), "true", "test_users", ";".join(test_emails), test_gmail_link])

    # User batches
    for idx, batch in enumerate(batches):
        batch_user_ids = []
        for user in users:
            if user.get('user_email') in batch:
                batch_user_ids.append(user.get('user_id'))

        gmail_link = generate_gmail_url(batch, subject, body, email_field)
        writer.writerow([idx + 1, len(batch), "false", ";".join(batch_user_ids), ";".join(batch), gmail_link])

    return output.getvalue()


# --- Session State ---
if 'ebg_parsed_ids' not in st.session_state:
    st.session_state.ebg_parsed_ids = []
if 'ebg_parse_errors' not in st.session_state:
    st.session_state.ebg_parse_errors = []
if 'ebg_syntax_errors' not in st.session_state:
    st.session_state.ebg_syntax_errors = []
if 'ebg_fetched_users' not in st.session_state:
    st.session_state.ebg_fetched_users = None
if 'ebg_male_csv' not in st.session_state:
    st.session_state.ebg_male_csv = None
if 'ebg_female_csv' not in st.session_state:
    st.session_state.ebg_female_csv = None
if 'ebg_selected_template' not in st.session_state:
    st.session_state.ebg_selected_template = get_default_template()

# --- Template Management Sidebar ---
def on_template_change():
    """Callback when template selection changes."""
    selected = st.session_state.ebg_template_selector
    if selected == "No Template":
        st.session_state.ebg_selected_template = None
        # Set empty values
        st.session_state.ebg_subject_male = ""
        st.session_state.ebg_content_male = ""
        st.session_state.ebg_subject_female = ""
        st.session_state.ebg_content_female = ""
    else:
        st.session_state.ebg_selected_template = selected
        # Load template values directly into session state
        template_data = get_template(selected)
        if template_data:
            st.session_state.ebg_subject_male = template_data.get("male", {}).get("subject", "")
            st.session_state.ebg_content_male = template_data.get("male", {}).get("content", "")
            st.session_state.ebg_subject_female = template_data.get("female", {}).get("subject", "")
            st.session_state.ebg_content_female = template_data.get("female", {}).get("content", "")

with st.sidebar:
    st.header("Template Manager")

    # Clear add form if flag is set
    if st.session_state.get('ebg_clear_add_form'):
        for key in ['ebg_new_name', 'ebg_new_male_subject', 'ebg_new_male_content', 'ebg_new_female_subject', 'ebg_new_female_content']:
            if key in st.session_state:
                del st.session_state[key]
        del st.session_state.ebg_clear_add_form

    templates = get_template_names()
    default_template = get_default_template()

    # Template Selector
    template_options = ["No Template"] + templates
    current_idx = 0
    if st.session_state.ebg_selected_template and st.session_state.ebg_selected_template in templates:
        current_idx = template_options.index(st.session_state.ebg_selected_template)

    st.selectbox(
        "Select Template",
        template_options,
        index=current_idx,
        key="ebg_template_selector",
        on_change=on_template_change
    )

    # Show default indicator
    if default_template:
        st.caption(f"Default: **{default_template}**")
    else:
        st.caption("Default: *No template*")

    st.divider()

    # --- Add New Template ---
    with st.expander("Add New Template", expanded=False):
        new_name = st.text_input("Template Name", placeholder="My Template", key="ebg_new_name")

        st.markdown("**Male Content**")
        new_male_subject = st.text_input("Male Subject", key="ebg_new_male_subject")
        new_male_content = st.text_area("Male Content", height=100, key="ebg_new_male_content")

        st.markdown("**Female Content**")
        new_female_subject = st.text_input("Female Subject", key="ebg_new_female_subject")
        new_female_content = st.text_area("Female Content", height=100, key="ebg_new_female_content")

        if st.button("Add Template", type="primary", use_container_width=True, key="ebg_add_template_btn"):
            if new_name:
                if new_name in templates:
                    st.error("Template already exists!")
                else:
                    add_template(new_name, new_male_subject, new_male_content, new_female_subject, new_female_content)
                    # Select the newly added template
                    st.session_state.ebg_selected_template = new_name
                    st.session_state.ebg_subject_male = new_male_subject
                    st.session_state.ebg_content_male = new_male_content
                    st.session_state.ebg_subject_female = new_female_subject
                    st.session_state.ebg_content_female = new_female_content
                    # Set flag to clear form on next run
                    st.session_state.ebg_clear_add_form = True
                    st.success(f"Added: {new_name}")
                    st.rerun()
            else:
                st.error("Template name required!")

    # --- Manage Existing Templates ---
    if templates:
        with st.expander("Manage Templates", expanded=False):
            manage_template = st.selectbox("Select Template to Manage", templates, key="ebg_manage_select")

            if manage_template:
                # Rename
                st.markdown("**Rename**")
                new_template_name = st.text_input("New Name", value=manage_template, key="ebg_rename_name")
                if st.button("Rename", key="ebg_rename_btn"):
                    if new_template_name and new_template_name != manage_template:
                        if new_template_name in templates:
                            st.error("Name already exists!")
                        else:
                            rename_template(manage_template, new_template_name)
                            if st.session_state.ebg_selected_template == manage_template:
                                st.session_state.ebg_selected_template = new_template_name
                            st.success("Renamed!")
                            st.rerun()

                st.markdown("---")

                # Set as Default
                if st.button("Set as Default", key="ebg_set_default_btn", use_container_width=True):
                    set_default_template(manage_template)
                    st.success(f"Default set to: {manage_template}")
                    st.rerun()

                # Delete
                if st.button("Delete Template", type="secondary", key="ebg_delete_btn", use_container_width=True):
                    delete_template(manage_template)
                    st.warning(f"Deleted: {manage_template}")
                    if st.session_state.ebg_selected_template == manage_template:
                        st.session_state.ebg_selected_template = None
                    st.rerun()

# --- Main UI ---
st.title("Email Batch Generator")
st.caption("Generate Gmail batch links for sending emails to users")

# User IDs Input
st.subheader("1. User IDs Input")
st.markdown("""
**Supported formats:**
- List format: `["id1", "id2", "id3"]`
- Quoted comma separated: `"id1", "id2", "id3"`
- Plain comma separated: `id1, id2, id3`
- Newline separated (one per line)
""")

user_ids_input = st.text_area(
    "Enter User IDs",
    height=200,
    placeholder='Paste user IDs here...\n\nExamples:\n"b6e3260c-2150-4b24-a249-ce48807fcc19", "43f1bb97-25bf-4835-97bf-4be3fd25224c"\n\nOR\n\nb6e3260c-2150-4b24-a249-ce48807fcc19\n43f1bb97-25bf-4835-97bf-4be3fd25224c',
    key="ebg_user_ids_input"
)

# Parse button
if st.button("Parse & Validate", type="primary", key="ebg_parse_btn"):
    if user_ids_input:
        # Check syntax first
        st.session_state.ebg_syntax_errors = detect_syntax_errors(user_ids_input)

        # Parse IDs
        parsed_ids, parse_errors = parse_user_ids(user_ids_input)
        st.session_state.ebg_parsed_ids = parsed_ids
        st.session_state.ebg_parse_errors = parse_errors
        st.session_state.ebg_fetched_users = None  # Reset fetched users
        st.session_state.ebg_male_csv = None
        st.session_state.ebg_female_csv = None

# Display parsing results
if st.session_state.ebg_syntax_errors:
    st.error("Syntax Errors Found:")
    for err in st.session_state.ebg_syntax_errors:
        st.markdown(f"""
        <div style="background-color: #3d1f1f; padding: 10px; border-radius: 5px; margin: 5px 0; border-left: 4px solid #ff4b4b;">
            <strong>Line {err.get('line', '?')}:</strong> {err['message']}<br>
            {f"<code>{err.get('context', '')}</code>" if err.get('context') else ""}
        </div>
        """, unsafe_allow_html=True)

if st.session_state.ebg_parse_errors:
    st.warning(f"{len(st.session_state.ebg_parse_errors)} Invalid User ID(s):")
    for err in st.session_state.ebg_parse_errors:
        st.markdown(f"""
        <div style="background-color: #3d3d1f; padding: 10px; border-radius: 5px; margin: 5px 0; border-left: 4px solid #ffbb33;">
            <strong>#{err['position']}:</strong> {err['message']}<br>
            <code>{err.get('context', err.get('value', ''))}</code>
        </div>
        """, unsafe_allow_html=True)

if st.session_state.ebg_parsed_ids:
    st.success(f"{len(st.session_state.ebg_parsed_ids)} valid User IDs parsed")
    with st.expander("Show parsed IDs"):
        st.code("\n".join(st.session_state.ebg_parsed_ids))

st.divider()

# Email Content Section
st.subheader("2. Email Content")

# Load template values if a template is selected
selected_template_data = None
if st.session_state.ebg_selected_template:
    selected_template_data = get_template(st.session_state.ebg_selected_template)

# Default values (empty if no template)
default_male_subject = ""
default_male_content = ""
default_female_subject = ""
default_female_content = ""

if selected_template_data:
    default_male_subject = selected_template_data.get("male", {}).get("subject", "")
    default_male_content = selected_template_data.get("male", {}).get("content", "")
    default_female_subject = selected_template_data.get("female", {}).get("subject", "")
    default_female_content = selected_template_data.get("female", {}).get("content", "")
    st.info(f"Using template: **{st.session_state.ebg_selected_template}**")
else:
    st.warning("No template selected. Enter content manually or select a template from sidebar.")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Male**")
    subject_male = st.text_input("Subject (Male)", value=default_male_subject, key="ebg_subject_male")
    content_male = st.text_area(
        "Content (Male)",
        height=250,
        value=default_male_content,
        key="ebg_content_male"
    )

with col2:
    st.markdown("**Female**")
    if st.button("Copy from Male", key="ebg_copy_to_female"):
        st.session_state.ebg_subject_female = st.session_state.ebg_subject_male
        st.session_state.ebg_content_female = st.session_state.ebg_content_male
        st.rerun()

    subject_female = st.text_input(
        "Subject (Female)",
        value=st.session_state.get('ebg_subject_female', default_female_subject),
        key="ebg_subject_female"
    )
    content_female = st.text_area(
        "Content (Female)",
        height=250,
        value=st.session_state.get('ebg_content_female', default_female_content),
        key="ebg_content_female"
    )

st.divider()

# Test Emails Section
st.subheader("3. Test Emails")
test_emails_input = st.text_area(
    "Test Emails (one per line)",
    value=DEFAULT_TEST_EMAILS,
    height=150,
    key="ebg_test_emails"
)

st.divider()

# Generate Button
st.subheader("4. Generate Email Batches")

gen_col1, gen_col2 = st.columns([3, 1])

with gen_col2:
    email_field = st.selectbox(
        "Email Field",
        options=["bcc", "cc", "to"],
        index=0,
        key="ebg_email_field",
        help="Where to put recipient emails in Gmail link"
    )

with gen_col1:
    generate_clicked = st.button("Generate CSV Downloads", type="primary", disabled=len(st.session_state.ebg_parsed_ids) == 0, key="ebg_generate_btn", use_container_width=True)

if generate_clicked:
    if not st.session_state.ebg_parsed_ids:
        st.error("Please parse user IDs first!")
    else:
        with st.spinner("Fetching user data from Supabase..."):
            user_ids = st.session_state.ebg_parsed_ids

            # Batch queries to avoid PostgREST URL length limits
            BATCH_SIZE = 100
            user_data_all = []
            user_metadata_all = []

            for i in range(0, len(user_ids), BATCH_SIZE):
                batch = user_ids[i:i + BATCH_SIZE]

                # Fetch emails from user_data
                user_data_res = supabase.table("user_data").select("user_id, user_email").in_("user_id", batch).execute()
                user_data_all.extend(user_data_res.data or [])

                # Fetch gender from user_metadata
                user_metadata_res = supabase.table("user_metadata").select("user_id, gender").in_("user_id", batch).execute()
                user_metadata_all.extend(user_metadata_res.data or [])

            if not user_data_all:
                st.error("No users found in database!")
            else:
                # Merge data
                users = []
                for ud in user_data_all:
                    metadata = next((um for um in user_metadata_all if um['user_id'] == ud['user_id']), None)
                    users.append({
                        "user_id": ud['user_id'],
                        "user_email": ud.get('user_email'),
                        "gender": metadata.get('gender') if metadata else None
                    })

                st.session_state.ebg_fetched_users = users

                # Separate by gender
                male_users = [u for u in users if u.get('gender', '').lower() == 'male' and u.get('user_email')]
                female_users = [u for u in users if u.get('gender', '').lower() == 'female' and u.get('user_email')]

                # Parse test emails
                test_emails = [e.strip() for e in test_emails_input.strip().split('\n') if e.strip()]

                # Generate batches
                male_emails = [u['user_email'] for u in male_users]
                female_emails = [u['user_email'] for u in female_users]

                male_batches = batch_emails(male_emails, subject_male, content_male)
                female_batches = batch_emails(female_emails, subject_female, content_female)

                # Generate CSVs
                st.session_state.ebg_male_csv = generate_csv_content(male_batches, male_users, subject_male, content_male, test_emails, "male", email_field)
                st.session_state.ebg_female_csv = generate_csv_content(female_batches, female_users, subject_female, content_female, test_emails, "female", email_field)

                # Show summary
                st.success("CSVs Generated!")

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Users Fetched", len(users))
                with col2:
                    st.metric("Male Users", f"{len(male_users)} ({len(male_batches)} batches)")
                with col3:
                    st.metric("Female Users", f"{len(female_users)} ({len(female_batches)} batches)")

                # Show warnings
                no_email = [u for u in users if not u.get('user_email')]
                no_gender = [u for u in users if not u.get('gender')]
                not_found = set(user_ids) - set(u['user_id'] for u in users)

                if no_email:
                    st.warning(f"{len(no_email)} user(s) without email")
                if no_gender:
                    st.warning(f"{len(no_gender)} user(s) without gender")
                if not_found:
                    st.warning(f"{len(not_found)} user ID(s) not found in database")
                    with st.expander("Show not found IDs"):
                        st.code("\n".join(not_found))

# Download buttons
if st.session_state.ebg_male_csv and st.session_state.ebg_female_csv:
    st.divider()
    st.subheader("Download CSVs")

    timestamp = datetime.now().strftime("%Y-%m-%d")

    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
            label="Download Male CSV",
            data=st.session_state.ebg_male_csv,
            file_name=f"male_email_batches_{timestamp}.csv",
            mime="text/csv",
            use_container_width=True
        )

    with col2:
        st.download_button(
            label="Download Female CSV",
            data=st.session_state.ebg_female_csv,
            file_name=f"female_email_batches_{timestamp}.csv",
            mime="text/csv",
            use_container_width=True
        )
