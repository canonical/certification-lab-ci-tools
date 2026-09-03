#!/usr/bin/env python3
# encoding: UTF-8
# Copyright (c) 2018-2019 Canonical Ltd.
#
# Authors:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
from launchpadlib.launchpad import Launchpad
from lazr.restfulclient.errors import NotFound
import datetime
import hashlib
import pygsheets
import re
import logging
import sys

from fnmatch import fnmatch

"""
This programs keeps ODM projects' bugs in sync with the Somerville project.

For more information see: goo.gl/ajiwG4
"""
try:
    import odm_sync_config
except ImportError as exc:
    raise SystemExit("Problem with reading the config: {}".format(exc))

status_list = [
    "New",
    "Confirmed",
    "Triaged",
    "In Progress",
    "Fix Committed",
    "Invalid",
    "Won't Fix",
    "Incomplete",
]
ODM_COMMENT_HEADER = "[Automated ODM-sync-tool comment]\n"


logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


def find_bug_ref(text):
    """
    Search the `text` for bug's url and return the number of the first
    bug found, or None when bug URL is not found.

    >>> find_bug_ref('https://bugs.launchpad.net/bugs/123')
    123
    >>> find_bug_ref('Foobar 3000')
    >>> find_bug_ref('twoline\\nhttps://bugs.launchpad.net/bugs/456')
    456
    >>> find_bug_ref('https://bugs.launchpad.net/bugs/onetwo')
    >>> find_bug_ref('Bug #1834180')
    1834180
    """
    match = re.compile(r"https://bugs.launchpad.net/bugs/(\d+)").search(text)
    if match:
        return int(match.groups()[0])
    match = re.compile(r"Bug #(\d+)").search(text)
    if match:
        return int(match.groups()[0])


class SyncTool:
    def __init__(self, credentials_file, config):
        self._cfg = config
        self._owners_spreadsheet = OwnersSpreadsheet(config)
        self.lp = Launchpad.login_with(
            "sync-odm-bugs", "production", credentials_file=credentials_file
        )
        self.bug_db = dict()
        self.proj_db = dict()
        self.bug_xref_db = dict()
        self.platform_map = dict()
        for proj in self._cfg.odm_projects + [self._cfg.umbrella_project]:
            self.bug_db[proj] = dict()
            self.proj_db[proj] = self.lp.projects[proj]
        self.user_db = dict()
        for person in set(self._owners_spreadsheet.owners.values()):
            self.user_db[person] = self.lp.people[person]

    def verify_bug(self, bug):
        comment = ""
        last_updated = bug.bug.date_last_updated
        if (
            bug.status == "Incomplete"
            and (datetime.datetime.now(last_updated.tzinfo) - last_updated).days > 14
        ):
            comment = "No activity for more than 14 days"
            logging.info("%s on bug %s", comment, bug.bug.id)
            self._add_comment(bug, comment)
            bug.status = "Invalid"
            bug.lp_save()
        if bug.status == "Incomplete":
            return False
        if "checkbox" not in bug.bug.tags and "cpm-reviewed" not in bug.bug.tags:
            comment = (
                "Bug report isn't tagged with either 'checkbox' or"
                " 'cpm-reviewed'. Marking as incomplete."
            )
            self._add_comment(bug, comment)
            bug.status = "Incomplete"
            bug.lp_save()
            return False
        for tag in bug.bug.tags:
            if tag in self._owners_spreadsheet.owners.keys():
                self.platform_map[bug.bug.id] = tag
                break
        else:
            comment = "Bug report isn't tagged with a platform tag"
            self._add_comment(bug, comment)
            bug.status = "Incomplete"
            bug.lp_save()
        for msg in bug.bug.messages:
            atts = [a for a in msg.bug_attachments]
            if any([fnmatch(a.title, "sosreport*.tar.xz") for a in atts]):
                break
        else:
            comment = "Missing sosreport attachment"
            self._add_comment(bug, comment)
            bug.status = "Incomplete"
            bug.lp_save()

        mandatory_items = [
            "expected result",
            "actual result",
            "sku",
            "bios version",
            "image/manifest",
            "cpu",
            "gpu",
            "reproduce steps",
            "qmetry id",
        ]

        missing = []
        for item in mandatory_items:
            if not re.search(item, bug.bug.description, flags=re.IGNORECASE):
                missing.append(item)
        if missing:
            comment = "Marking as Incomplete because of missing information: {}".format(
                ", ".join(missing)
            )
            self._add_comment(bug, comment)
            bug.status = "Incomplete"
            bug.lp_save()

        return not comment

    def add_bug_to_db(self, bug):
        self.bug_db[bug.bug_target_name][bug.bug.title] = bug.bug

    def build_bug_db(self):
        for proj, proj_bugs in self.bug_db.items():
            if proj == self._cfg.umbrella_project:
                continue
            for bug_title, bug in proj_bugs.items():
                logging.debug("Checking if %s is in the umbrella", bug_title)
                # look for bug in the umbrella project
                for u_title, u_bug in self.bug_db[self._cfg.umbrella_project].items():
                    if u_bug.messages.total_size >= 2:
                        first_comment = u_bug.messages[1].content
                        if first_comment.startswith(ODM_COMMENT_HEADER):
                            bug_no = find_bug_ref(first_comment)
                            if bug_no == bug.id:
                                logging.debug(
                                    "bug %s already defined in umbrella", u_title
                                )
                                self.bug_xref_db[bug.id] = u_bug.id
                                self.bug_xref_db[u_bug.id] = bug.id
                                break
                else:
                    bug_task = bug.bug_tasks[0]
                    if bug.id not in self.platform_map.keys():
                        logging.error(
                            "%s project is not listed in the Management Spreadsheet",
                            proj,
                        )
                        owner = ""
                    else:
                        owner = self._owners_spreadsheet.owners[
                            self.platform_map[bug.id]
                        ]
                    new_bug = self.file_bug(
                        self._cfg.umbrella_project,
                        "[ODM bug] " + bug_title,
                        bug.description,
                        bug_task.status,
                        bug.tags + [proj, "odm-bug"],
                        owner,
                    )
                    self.add_bug_to_db(new_bug.bug_tasks[0])
                    self.bug_xref_db[bug.id] = new_bug.id
                    self.bug_xref_db[new_bug.id] = bug.id
                    message = (
                        "This bug is from [{}] Launchpad project."
                        "\nPlease refer to Bug #{}".format(proj, bug.id)
                    )
                    self._add_comment(new_bug.bug_tasks[0], message)
                    message = (
                        "This bug has been synced to {} Launchpad"
                        " project successfully.\nPlease refer to Bug"
                        " #{}".format(self._cfg.umbrella_project, new_bug.id)
                    )
                    self._add_comment(bug_task, message)

    def sync_all(self):
        for proj in self._cfg.odm_projects:
            for odm_bug_name, odm_bug in self.bug_db[proj].items():
                umb_bug = self.lp.bugs[self.bug_xref_db[odm_bug.id]]
                odm_messages = [msg for msg in odm_bug.messages][1:]
                umb_messages = [msg for msg in umb_bug.messages][1:]
                odm_comments = []

                def fake_content(msg):
                    """Create a fake content out of attachment titles."""
                    new_content = "__Empty_comment__attachments: "

                    def att_hash(att):
                        hash_cache = {}
                        if att.self_link not in hash_cache.keys():
                            hash_cache[att.self_link] = "{}-{}".format(
                                att.title,
                                hashlib.sha1(att.data.open().read()).hexdigest(),
                            )
                        return hash_cache[att.self_link]

                    new_content += ", ".join([att_hash(a) for a in msg.bug_attachments])
                    return new_content

                def trim_messages(messages):
                    """Remove automatically added headers from the comments."""
                    trimmed_comments = []
                    for msg in messages:
                        if msg.content.startswith(ODM_COMMENT_HEADER):
                            trimmed_lines = []
                            for line in msg.content.splitlines():
                                if line.startswith("[") and line.endswith("]"):
                                    continue
                                trimmed_lines.append(line)
                            new_comment = "\n".join(trimmed_lines)
                            if not new_comment:
                                new_comment = fake_content(msg)
                            trimmed_comments.append(new_comment)
                        else:
                            trimmed_comments.append(msg.content)
                    return trimmed_comments

                for msg in odm_messages:
                    odm_comments.append(msg.content or fake_content(msg))
                for msg in odm_messages:
                    trimmed_umb_comments = trim_messages(umb_messages)
                    if msg.content and msg.content in trimmed_umb_comments:
                        continue
                    if msg.content.startswith(ODM_COMMENT_HEADER):
                        continue
                    if not msg.content and (fake_content(msg) in trimmed_umb_comments):
                        continue
                    logging.info(
                        "Adding missing comment from %s to %s",
                        proj,
                        self._cfg.umbrella_project,
                    )
                    # LP lets us view the hidden comments, but not their
                    # attachments
                    try:
                        attachments = [a for a in msg.bug_attachments]
                        content = "[Original comment posted on {} by {}]\n{}".format(
                            msg.date_created.strftime("%Y-%m-%d %H:%M:%S"),
                            msg.owner.name,
                            msg.content,
                        )
                        self._add_comment(umb_bug.bug_tasks[0], content, attachments)
                    except NotFound as exc:
                        logging.info("Skipping comment (Probably hidden)")
                for msg in umb_messages:
                    trimmed_odm_comments = trim_messages(odm_messages)
                    if msg.content and msg.content in trimmed_odm_comments:
                        continue
                    if msg.content.startswith(ODM_COMMENT_HEADER):
                        continue
                    if not msg.content and (fake_content(msg) in trimmed_odm_comments):
                        continue
                    logging.info(
                        "Adding missing comment from %s to %s",
                        self._cfg.umbrella_project,
                        proj,
                    )
                    try:
                        attachments = [a for a in msg.bug_attachments]
                        content = "[Original comment posted on {} by {}]\n{}".format(
                            msg.date_created.strftime("%Y-%m-%d %H:%M:%S"),
                            msg.owner.name,
                            msg.content,
                        )
                        self._add_comment(odm_bug.bug_tasks[0], content, attachments)
                    except NotFound as exc:
                        logging.info("Skipping comment (Probably hidden)")
                self._sync_meta(odm_bug, umb_bug)

    def _sync_meta(self, bug1, bug2):
        if bug1.date_last_updated > bug2.date_last_updated:
            src = bug1
            dest = bug2
        else:
            src = bug2
            dest = bug1
        changed = False
        # for comparing titles we need to make sure the prefix is removed
        src_title = src.title.split(self._cfg.umbrella_prefix, maxsplit=1)[-1]
        dest_title = dest.title.split(self._cfg.umbrella_prefix, maxsplit=1)[-1]
        if src_title != dest_title:
            if src.title.startswith(self._cfg.umbrella_prefix):
                # copying FROM umbrella bug so the prefix is already stripped
                dest.title = src_title
            else:
                # copying TO umbrella bug so we need to add the prefix
                dest.title = self._cfg.umbrella_prefix + src_title
            changed = True

        if src.description != dest.description:
            dest.description = src.description
            changed = True

        if src.tags != dest.tags:
            dest.tags = src.tags
            changed = True

        # get bug_task for both bugs
        src_bt = src.bug_tasks[0]
        dest_bt = dest.bug_tasks[0]
        bt_changed = False

        for f in ["assignee", "status", "milestone", "importance"]:
            if getattr(src_bt, f) != getattr(dest_bt, f):
                setattr(dest_bt, f, getattr(src_bt, f))
                bt_changed = True

        if changed:
            dest.lp_save()
        if bt_changed:
            dest_bt.lp_save()

    def file_bug(self, project, title, description, status, tags, assignee):
        bug = self.lp.bugs.createBug(
            title=title,
            description=description,
            tags=tags,
            target=self.proj_db[project],
        )
        bug.lp_save()
        task = bug.bug_tasks[0]
        task.status = status
        if assignee:
            task.assignee = self.user_db[assignee]
        task.lp_save()
        return bug

    def _add_comment(self, bug, message, attachments=None):
        # XXX: I think LP allows one attachment per bug message
        message = ODM_COMMENT_HEADER + message
        if attachments:
            prohibited_chars = "/"
            new_filename = attachments[0].title
            for c in prohibited_chars:
                new_filename = new_filename.replace(c, "_")
            bug.bug.addAttachment(
                data=attachments[0].data.open().read(),
                comment=message,
                filename=new_filename,
                is_patch=attachments[0].type == "Patch",
            )
        else:
            bug.bug.newMessage(content=message)

    def main(self):
        start_date = datetime.datetime.strptime(self._cfg.start_date, "%Y-%m-%d")
        for p in self._cfg.odm_projects:
            project = self.lp.projects[p]
            bug_tasks = project.searchTasks(
                status=status_list, tags=["dm-reviewed"], created_since=start_date
            )
            for bug in bug_tasks:
                if self.verify_bug(bug):
                    self.add_bug_to_db(bug)
        project = self.lp.projects[self._cfg.umbrella_project]
        bug_tasks = project.searchTasks(
            status=status_list, tags=self._cfg.odm_projects, created_since=start_date
        )
        for bug in bug_tasks:
            self.add_bug_to_db(bug)
        self.build_bug_db()
        self.sync_all()


class OwnersSpreadsheet:
    def __init__(self, config):
        self._cfg = config
        self._gcli = pygsheets.authorize()
        self._owners = None

    @property
    def owners(self):
        if not self._owners:
            sheet = self._gcli.open_by_key(self._cfg.tracking_doc_id)
            column_j = sheet.worksheet_by_title("Platforms").get_col(10)[2:]
            OWNER_COLUMN = 49
            column_ar = sheet.worksheet_by_title("Platforms").get_col(OWNER_COLUMN)[2:]
            self._owners = dict()
            for platform, raw_owner in zip(column_j, column_ar):
                if not raw_owner:
                    logging.warning("%s platform doesn't have an owner!", platform)
                    continue
                owner = self._cfg.lp_names.get(raw_owner)
                if not owner:
                    logging.warning("No mapping to launchpad id for %s", raw_owner)
                    continue
                if not platform:
                    continue
                if platform in self._owners.keys():
                    logging.debug("%s platform already registered", platform)
                    if self._owners[platform] != owner:
                        logging.warning(
                            "And the owner is different! Previous %s, now %s",
                            self._owners[platform],
                            owner,
                        )
                self._owners[platform] = owner
        return self._owners


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--credentials", default=None, help="Path to launchpad credentials file"
    )
    args = parser.parse_args()
    sync_tool = SyncTool(args.credentials, odm_sync_config)
    sync_tool.main()


if __name__ == "__main__":
    raise SystemExit(main())
