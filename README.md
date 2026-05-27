# Python Gmail Sender Script

This script provides a simple but powerful way to automate sending emails via a Gmail SMTP server, using pure Python without any external dependencies.

## Libraries Used

This script relies entirely on standard built-in Python libraries, so no `pip install` is required:
*   `smtplib`
*   `email.message` (`EmailMessage`)
*   `email.utils` (`make_msgid`)
*   `mimetypes`
*   `os`

## Features & Methods Used
The `send_email.py` script utilizes the following built-in Python libraries to construct and transmit fully-featured emails:

### 1. `smtplib`
*   **Purpose:** Handles the actual communication with Gmail's email servers using the Simple Mail Transfer Protocol (SMTP).
*   **Methods Used:**
    *   `smtplib.SMTP_SSL('smtp.gmail.com', 465)`: Establishes a secure, encrypted connection to Google's SMTP server on port 465.
    *   `server.login(email, password)`: Authenticates your account (Requires an App Password).
    *   `server.send_message(msg)`: Transmits the final crafted `EmailMessage` object to the recipient.
    *   `server.quit()`: Safely closes the connection to the server.

### 2. `email.message.EmailMessage`
*   **Purpose:** The core class for constructing the email itself. It acts like a container where we set the headers (To, From, Subject) and the body content.
*   **Methods Used:**
    *   `msg['Subject'] = ...` (Dictionary assignment): Sets standard email headers. We also use this to inject the `Sensitivity` and `Importance` headers for the **Confidential Mode** feature.
    *   `msg.set_content(body_text)`: Sets the fallback plain-text version of the email.
    *   `msg.add_alternative(html_content, subtype='html')`: Attaches the HTML version of the email (which enables **Links, Emojis, and Signatures**). The email client chooses to display this over the plain-text version if supported.
    *   `msg.add_attachment(...)`: Used to attach regular files like PDFs, ZIPs, or documents to the bottom of the email.
    *   `msg.get_payload()[1].add_related(...)`: This advanced method is used specifically for **Inline Photos**. It attaches the image directly to the HTML payload (the 2nd item, index `1`) rather than the root email, allowing the HTML to reference it using a `cid:` tag.

### 3. `mimetypes`
*   **Purpose:** Automatically determines the correct format (MIME type) of the files you are attaching.
*   **Methods Used:**
    *   `mimetypes.guess_type(filepath)`: Examines a file's extension (e.g., `.jpg`, `.pdf`, `.csv`) and returns the appropriate classification like `image/jpeg` or `application/pdf`. This ensures the recipient's computer knows exactly how to open the file we attached.

### 4. `email.utils`
*   **Purpose:** Provides utility functions for parsing and formatting email data.
*   **Methods Used:**
    *   `make_msgid()`: Generates a globally unique identifier (e.g., `<12345.67890@domain.com>`). We use this specifically for **Inline Photos**, generating a unique `Content-ID` (CID) so the HTML `<img>` tag knows exactly which attached file to display.

### 5. `os`
*   **Purpose:** Used for interacting with the operating system's file system structure.
*   **Methods Used:**
    *   `os.path.isfile(filepath)`: Verifies that the file you want to attach actually exists before the script attempts to read it, preventing crashes.
    *   `os.path.basename(filepath)`: Extracts just the filename (like `report.pdf`) from a full absolute path (like `C:/Documents/report.pdf`) so the attachment displays correctly in the recipient's inbox.
