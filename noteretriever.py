import config
import os
import pickle
import shutil
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from base64 import urlsafe_b64decode, urlsafe_b64encode
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from mimetypes import guess_type as guess_mime_type

# Request all access (permission to read/send/receive emails, manage the inbox, and more)
SCOPES = ['https://mail.google.com/']
address = "sprousecal.rocketnotes@gmail.com"


def authentication():
    """Authenticates from the credentials.json file and returns a service"""
    creds = None
    # the file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    # if there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # save the credentials for the next run
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)
    return build('gmail', 'v1', credentials=creds)


def search_messages(service, query):
    """Search the inbox for emails matching a query"""
    result = service.users().messages().list(userId='me', q=query).execute()
    messages = []
    if 'messages' in result:
        messages.extend(result['messages'])
    while 'nextPageToken' in result:
        page_token = result['nextPageToken']
        result = service.users().messages().list(userId='me', q=query, pageToken=page_token).execute()
        if 'messages' in result:
            messages.extend(result['messages'])
    return messages


def get_message_attachments(service, message, save_location="attachments"):
    """ Downloads attachments from an email """

    def get_size_format(b, factor=1024, suffix="B"):
        """
        Scale bytes to its proper byte format
        e.g:
            1253656 => '1.20MB'
            1253656678 => '1.17GB'
        """
        for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
            if b < factor:
                return f"{b:.2f}{unit}{suffix}"
            b /= factor
        return f"{b:.2f}Y{suffix}"

    def parse_parts(parts):
        """ Utility function that parses the content of an email """
        for part in parts:
            filename = part.get("filename")
            body = part.get("body")
            if part.get("parts"):
                # recursively call this function when we see that a part
                # has parts inside
                parse_parts(part.get("parts"))
            if part.get("mimeType") == "text/plain" or part.get("mimeType") == "index.html":
                continue
            else:
                # attachment other than a plain text or HTML
                for part_header in part.get("headers"):
                    if part_header.get("name") == "Content-Disposition":
                        if "attachment" in part_header.get("value"):
                            # we get the attachment ID
                            # and make another request to get the attachment itself
                            print("Saving the file:", filename, "size:", get_size_format(body.get("size")))
                            attachment_id = body.get("attachmentId")
                            attachment = service.users().messages() \
                                .attachments().get(id=attachment_id, userId='me', messageId=message['id']).execute()
                            data = attachment.get("data")

                            os.makedirs(save_location, exist_ok=True)
                            filepath = os.path.join(save_location, filename)
                            if os.path.isfile(filepath):
                                counter = 1
                                while os.path.isfile(filepath):
                                    filepath = os.path.join(
                                        save_location, f"{filename.split('.')[0]}({counter}){filename.split('.')[1]}")
                                    counter += 1

                            if data:
                                with open(filepath, "wb") as f:
                                    f.write(urlsafe_b64decode(data))

    msg = service.users().messages().get(userId='me', id=message['id'], format='full').execute()
    parse_parts(msg['payload'].get("parts"))


def download_all_emails():
    """ Authenticates a connection to gmail and downloads all attachments available from unread emails """
    email_service = authentication()
    results = search_messages(email_service, "is:unread")
    for email in results:
        email_service.users().messages().modify(userId="me", id=email["id"],
                                                body={'removeLabelIds': ['UNREAD']}).execute()
        get_message_attachments(email_service, email)


def sort_downloads():
    # TODO: NEEDS SUPER CLEANUP
    for file in os.listdir("attachments"):
        if not os.path.isfile(os.path.join("attachments", file)):
            continue
        for key, val in config.save_location.items():
            os.makedirs(os.path.abspath(config.default_save_location), exist_ok=True)
            shutil.copy2(os.path.join("attachments", file), os.path.join(config.default_save_location, os.path.basename(file)))
            if key.lower() in file.lower():
                for save_location in val:
                    os.makedirs(os.path.join(save_location), exist_ok=True)
                    shutil.copy2(os.path.join("attachments", file), os.path.join(save_location, os.path.basename(file)))
        os.remove(os.path.join("attachments", file))


# TODO: Cleanup
# TODO: Error proofing (file not exist, duplicate file names)
# TODO: Self scheduled runs
# TODO: Success notification
if __name__ == "__main__":
    download_all_emails()
    sort_downloads()
