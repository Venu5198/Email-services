import smtplib
from email.message import EmailMessage
import os
import mimetypes
from email.utils import make_msgid

def send_email(sender_email, sender_password, receiver_email, subject, body_text, 
               body_html=None, attachments=None, inline_photos=None, signature_html=None,
               is_confidential=False):
    """
    Sends an email using Gmail's SMTP server, with support for attachments, HTML, inline photos, and sensitivity headers.
    """
    msg = EmailMessage()
    
    # Set standard email headers
    msg['Subject'] = subject
    msg['From'] = sender_email
    if isinstance(receiver_email, (list, tuple)):
        msg['To'] = ", ".join(receiver_email)
    else:
        msg['To'] = receiver_email
    
    # Toggle Confidential Mode (using standard SMTP sensitivity headers)
    # Note: True Gmail Confidential Mode (expiring emails) requires the Google Workspace API. 
    # Standard SMTP allows us to flag emails as confidential/private for email clients.
    if is_confidential:
        msg['Sensitivity'] = 'Company-Confidential'
        msg['Importance'] = 'High'

    # Add Plain Text Body
    msg.set_content(body_text)

    # Add HTML Body (Supports Links, Emojis, Drive Links, Formatting)
    if body_html or signature_html:
        html_content = str(body_html) if body_html else str(body_text).replace('\n', '<br>')
        
        # Add Signature if provided
        if signature_html:
            html_content = html_content + f"<br><br>-- <br>{signature_html}"

        # If inline photos are provided, we format them and append them to the HTML
        if inline_photos:
            for photo_path in inline_photos:
                if os.path.isfile(photo_path):
                    cid = str(make_msgid()).strip('<>') # Generate a unique Content-ID without brackets
                    html_content = html_content + f'<br><br><img src="cid:{cid}" alt="Inline Photo">'
                    # We temporarily store the path and CID to attach it later
                    # This is slightly hacky but works for keeping the function signature clean
                    if not hasattr(inline_photos, '_cid_map'):
                        inline_photos._cid_map = []
                    inline_photos._cid_map.append((photo_path, cid))
                else:
                    print(f"Warning: Inline photo not found - {photo_path}")

        msg.add_alternative(html_content, subtype='html')
        
    # Attach Inline Photos (must be done after add_alternative to ensure they are related to the HTML part properly)
    if inline_photos and hasattr(inline_photos, '_cid_map'):
        for photo_path, cid in inline_photos._cid_map:
            ctype, encoding = mimetypes.guess_type(str(photo_path))
            if ctype is None or encoding is not None:
                ctype = 'image/jpeg'
            maintype, subtype = ctype.split('/', 1) if isinstance(ctype, str) else ('image', 'jpeg')
            
            with open(str(photo_path), 'rb') as fp:
                # To make it an inline image, we set the Content-ID header
                html_part = msg.get_payload()[1]
                if isinstance(html_part, EmailMessage):
                    html_part.add_related(fp.read(), maintype=maintype, subtype=subtype, cid=f'<{cid}>')

    if attachments:
        for filepath in attachments:
            if os.path.isfile(filepath):
                # Guess the content type based on the file extension
                ctype, encoding = mimetypes.guess_type(str(filepath))
                if ctype is None or encoding is not None:
                    # No guess could be made, or the file is encoded (compressed)
                    # use a generic bag-of-bits type.
                    ctype = 'application/octet-stream'
                
                maintype, subtype = ctype.split('/', 1) if isinstance(ctype, str) else ('application', 'octet-stream')
                
                with open(filepath, 'rb') as fp:
                    msg.add_attachment(fp.read(),
                                       maintype=maintype,
                                       subtype=subtype,
                                       filename=os.path.basename(filepath))
            else:
                print(f"Warning: Attachment file not found - {filepath}")

    try:
        # Connect to Gmail's SMTP server using SSL
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        
        # Login to the email account
        server.login(sender_email, sender_password)
        
        # Send the email
        server.send_message(msg)
        print("Email sent successfully!")
        
    except Exception as e:
        print(f"Failed to send email. Error: {e}")
    finally:
        # Always close the connection
        try:
            server.quit()
        except:
            pass

if __name__ == '__main__':
    # ---------------------------------------------------------
    # CONFIGURATION
    # ---------------------------------------------------------
    # Replace these with your actual details, or use environment 
    # variables for better security: os.environ.get('EMAIL_USER')
    
    SENDER_EMAIL = 'venukrishnaya@gmail.com'
    
    # IMPORTANT: You MUST use an App Password here if 2FA (Two-Factor Authentication) 
    # is enabled on your Google account. Your regular login password won't work.
    SENDER_PASSWORD = 'xxxx xxxx xxxx xxxx' 

    RECEIVER_EMAIL = input("Enter the receiver's email address: ")

    EMAIL_SUBJECT = 'Test Email: Link, Emoji, Drive, Photo, Signature 🚀'
    
    # 1. Plain Text fallback for clients that don't support HTML
    EMAIL_BODY_TEXT = 'Hello! This is a test email sent using Python.'
    
    # 2. HTML Body: Supports Links, Emojis, formatting
    # Note: Emojis are fully supported via Unicode strings (🎉, 🚀, 😊)
    EMAIL_BODY_HTML = """
    <html>
        <body>
            <h3>Hello! 👋</h3>
            <p>This is a test email sent using Python.</p>
            <ul>
                <li><b>Insert Link:</b> Check out <a href="https://github.com">GitHub</a>.</li>
                <li><b>Emoji:</b> Python makes this so easy! 🐍✨</li>
                <li><b>Drive Link:</b> <a href="https://drive.google.com/drive/">View my Google Drive file here</a>.</li>
            </ul>
            <p>Here is an inline photo below:</p>
        </body>
    </html>
    """

    # 3. Signature Formatting (HTML)
    SIGNATURE = """
    <div style="font-family: Arial, sans-serif; color: #555;">
        <b>Venu Krishnaya</b><br>
        Software Engineer | <a href="mailto:venukrishnaya@gmail.com">venukrishnaya@gmail.com</a>
    </div>
    """

    # 4. Confidential Mode Toggle
    # Set to True to add 'Company-Confidential' and 'High Importance' headers.
    CONFIDENTIAL_MODE = True
    
    # 5. Regular File Attachments
    ATTACHMENTS = ['test_attachment.txt'] 

    # 6. Inline Photos (Will be embedded directly into the email body above the signature)
    # Leave empty if no inline photos are needed.
    INLINE_PHOTOS = [] # e.g., ['my_photo.jpg']
    
    send_email(
        sender_email=SENDER_EMAIL, 
        sender_password=SENDER_PASSWORD, 
        receiver_email=RECEIVER_EMAIL, 
        subject=EMAIL_SUBJECT, 
        body_text=EMAIL_BODY_TEXT,
        body_html=EMAIL_BODY_HTML,
        attachments=ATTACHMENTS,
        inline_photos=INLINE_PHOTOS,
        signature_html=SIGNATURE,
        is_confidential=CONFIDENTIAL_MODE
    )
