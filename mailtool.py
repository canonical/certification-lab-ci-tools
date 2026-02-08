#!/usr/bin/env python3

# This should only be run from a system with postfix installed

import argparse
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate

SMTPSERVER = os.environ.get('SMTP_SERVER', 'localhost')

ERROR_MSG = """
ERROR!
The email for this job was supposed to be located in {} but that file
wasn't generated for some reason. This almost never happens, so
look for something farther up in the job related to this subject for
clues as to what might have happened
"""


def get_args():
    parser = argparse.ArgumentParser(description='Simple Mail Tool')
    parser.add_argument('--to', '-t', required=True, help='To recipient')
    parser.add_argument('--subject', '-s', required=True, help='Subject')
    parser.add_argument('--attach', '-a', required=False, action='append',
                        help='Attach a file')
    parser.add_argument('messagefile',
                        help='File containing the message to send')
    return parser.parse_args()


def main():
    args = get_args()
    try:
        with open(args.messagefile, 'rt') as mailfile:
            body = mailfile.read()
    except Exception:
        body = ERROR_MSG.format(args.messagefile)

    send_mail(
        to=args.to, subject=args.subject, body=body, attachments=args.attach)


def send_mail(to=None, subject="(No Subject)", body=None, attachments=None):
    """ Send an email

    :param subject: Message subject, defaults to "(No Subject)"
    :param messagefile: Body of message as a string, defaults to None
    :param attachments: List of files containing attachments, defaults to None
    """
    # https://stackoverflow.com/q/41639660/1154487
    msg = MIMEMultipart('mixed')
    if body:
        body = ('<html><body>'
                '<font face="Courier New, Courier, monospace">'
                '<pre>' + body + '</pre>'
                '</font></body></html>')
        body_part = MIMEText(body, 'html')
        msg.attach(body_part)

    if attachments:
        for attach_file in attachments:
            try:
                with open(attach_file, 'rb') as attachment:
                    part = MIMEApplication(attachment.read())
                part.add_header('Content-Disposition', 'attachment',
                                filename=os.path.basename(attach_file))
                msg.attach(part)
            except Exception:
                print('Error attaching {}'.format(attach_file))

    msg['Subject'] = subject
    msg['From'] = 'noreply@canonical.com'
    msg['To'] = to
    msg['Date'] = formatdate(localtime=True)

    s = smtplib.SMTP(SMTPSERVER)
    s.send_message(msg)
    s.quit()


if __name__ == '__main__':
    main()
