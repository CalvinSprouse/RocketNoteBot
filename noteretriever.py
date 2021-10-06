import config
import os
import pickle
import shutil
from os import path as opath
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from base64 import urlsafe_b64decode


def authentication(credentials_file: str = "credentials.json", pickle_file: str = "credentials.pickle",
                   scopes: list = None):
    """Authenticates from the credentials.json file and returns a service"""
    if scopes is None:
        scopes = ["https://mail.google.com"]
    creds = None
    # the file credentials.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time
    if opath.exists(credentials_file):
        with open(pickle_file, "rb") as token:
            creds = pickle.load(token)
    # if there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, scopes)
            creds = flow.run_local_server(port=0)
        # save the credentials for the next run
        with open(pickle_file, "wb") as token:
            pickle.dump(creds, token)
    return build('gmail', 'v1', credentials=creds)


def search_messages(gmail_service, query):
    """Search the inbox for emails matching a query"""
    result = gmail_service.users().messages().list(userId='me', q=query).execute()
    messages = []
    if 'messages' in result:
        messages.extend(result['messages'])
    while 'nextPageToken' in result:
        page_token = result['nextPageToken']
        result = gmail_service.users().messages().list(userId='me', q=query, pageToken=page_token).execute()
        if 'messages' in result:
            messages.extend(result['messages'])
    return messages


def uniquify_filename(file_path: str) -> str:
    """ Appends (x) where x is a number such that the filepath becomes unique """
    file_save_dir = opath.dirname(file_path)
    file_name_no_ext = opath.basename(file_path)[:opath.basename(file_path).rindex(".")].replace(" ", "")
    ext = opath.basename(file_path)[opath.basename(file_path).rindex("."):]
    file_save_location = opath.join(file_save_dir, f"{file_name_no_ext}{ext}")
    if opath.isfile(file_save_location):
        counter = 1
        file_save_location = opath.join(file_save_dir, f"{file_name_no_ext}({counter}).{ext}")
    return file_save_location


def get_message_attachments(gmail_service, message, save_location: str):
    """ Downloads attachments from an email """

    def _parse_parts(parts):
        """
        Utility function that parses the content of an email
        Recursively finds message parts within parts
        """
        for part in parts:
            filename = part.get("filename")
            body = part.get("body")

            if part.get("parts"):
                _parse_parts(part.get("parts"))
            if part.get("mimeType") == "text/plain" or part.get("mimeType") == "index.html":
                continue
            # attachment other than a plain text or HTML
            for part_header in part.get("headers"):
                if part_header.get("name") == "Content-Disposition":
                    if "attachment" in part_header.get("value"):
                        # we get the attachment ID
                        # and make another request to get the attachment itself
                        print("Saving the file:", filename, "size:", body.get("size"))
                        attachment_id = body.get("attachmentId")
                        attachment = gmail_service.users().messages().attachments().get(
                            id=attachment_id, userId='me', messageId=message['id']).execute()
                        data = attachment.get("data")

                        os.makedirs(save_location, exist_ok=True)
                        filepath = uniquify_filename(opath.join(save_location, filename))

                        if data:
                            with open(filepath, "wb") as f:
                                f.write(urlsafe_b64decode(data))

    msg = gmail_service.users().messages().get(userId='me', id=message['id'], format='full').execute()
    _parse_parts(msg['payload'].get("parts"))


def safe_copy_file(src: str, dst: str, ensure_dst_exists: bool = True):
    """ Copy a file and ensure the dst dir exists and that the filename is unique"""
    assert opath.isfile(src)
    if ensure_dst_exists:
        os.makedirs(opath.dirname(dst), exist_ok=True)
    shutil.copy2(src, uniquify_filename(dst))
    print("File moved:", src, dst)


# TODO: Self scheduled runs
# TODO: Success notification

if __name__ == "__main__":
    attachment_save_dir = "attachments"
    os.makedirs(attachment_save_dir, exist_ok=True)
    
    # download all attachments from inbox and mark each email as read
    email_service = authentication()
    results = search_messages(email_service, "is:unread")
    for email in results:
        get_message_attachments(email_service, email, attachment_save_dir)
        email_service.users().messages().modify(userId="me", id=email["id"],
                                                body={'removeLabelIds': ['UNREAD']}).execute()
    print("Inbox attachments retrieved")

    # sort the downloaded attachments into folders based on their file names
    print(f"Sorting {len(os.listdir(attachment_save_dir))} files: {os.listdir(attachment_save_dir)}")
    if opath.isdir(attachment_save_dir):
        for file in os.listdir(attachment_save_dir):
            try:
                file_location = opath.join(attachment_save_dir, file)
                file_name = opath.basename(file)
                if not opath.isfile(file_location):
                    continue
                # compare the keys to the filename and save to the default directory always
                for key, val in config.save_location.items():
                    safe_copy_file(file_location, opath.join(config.default_save_location, file_name))

                    # if a match is found save the file to all locations in the value list
                    if key.lower() in file.lower().replace(" ", ""):
                        print(f"Match found {file_name} to {key} -> {val}")
                        for save_location in val:
                            safe_copy_file(file_location, opath.join(save_location, file_name))
                # finally remove the file from the attachments directory
                os.remove(file_location)
            except AssertionError:
                print(f"File {file} is not a file")
