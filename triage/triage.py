#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import csv
import datetime
import markdown
import requests
import StringIO

MOCK_INPUT='''"Bug ID","Product","Component","Reporter","Assignee","Status","Resolution","Summary","Changed"
1147674,"Firefox","Untriaged","taylor.a.huston","nobody","UNCONFIRMED","---","Memory leaks in Firefox Developer Edition x64","2015-04-14 13:06:29"
1157839,"Core","JavaScript Engine","sphink","nobody","NEW","---","Investigate using refcounted strings for wrapping","2015-04-23 13:24:05"
1155371,"Core","DOM","erahm","erahm","ASSIGNED","---","Include DOMMediaStream and MediaSource object URLs in memory reports","2015-04-23 00:47:24"'''

COMMENTS_REST_QUERY='https://bugzilla.mozilla.org/rest/bug/%s/comment?include_fields=creator'

TRIAGE_CSV = ("https://bugzilla.mozilla.org/buglist.cgi?bug_status=UNCONFIRMED&"
              "bug_status=NEW&bug_status=ASSIGNED&bug_status=REOPENED&"
              "columnlist=product%2Ccomponent%2Creporter%2Cassigned_to%2Cbug_status%2Cresolution%2Cshort_desc%2Cchangeddate&"
              "query_format=advanced&resolution=---&resolution=DUPLICATE&"
              "status_whiteboard=MemShrink%5B%5E%3A%5D&"
              "status_whiteboard_type=regexp&ctype=csv&human=1")

SHORT_URL_FMT = "https://bugzil.la/%s"

# Mapping of bugzilla name to IRC nick for memshrink team members.
MEMSHRINKERS = {
        "erahm": "erahm",
        "n.nethercote": "njn",
        "nfroyd": "froydnj",
        "continuation": "mccr8",
        "jld": "jld",
        "khuey": "khuey",
}


TRIAGE_HEADER = """### Agenda ###

_(Add name and topic to discuss here)_

### Bug List ###

Vote for:

- **P1** High importance, will follow up periodically
- **P2** Important issue, possibly already being worked on
- **P3** Real issue, someone will get to it if they have time
- **moreinfo** We need logs, or clarifying information
- **invalid** Misclassified, remove the MemShrink tag
"""

TRIAGE_URL = "http://mzl.la/1yYeaGL"

TRIAGE_URL_TEMPLATE = """
**Triage URL:** [%s](%s)
"""

def get_commentors(bug_id):
    """Gets the bz names of commentors on the given bug"""
    response = requests.get(COMMENTS_REST_QUERY % bug_id).json()
    bug_comments = response['bugs'][bug_id]['comments']
    return set( x['creator'].split('@')[0] for x in bug_comments )


def generate_triage_text(triage_csv_url, triage_header, triage_bugzilla_url=None, team_mapping=None):
    """
    Builds a summary useful for triaging bugs via a multiuser text editor such as etherpad.

    :param triage_csv_url: URL to a bugzilla csv query. This should be configured to have:
                           Bug ID''Product', 'Component', 'Summary', and 'Reporter' fields.
    :param triage_header: Preamble text, perhaps explaining how bugs are triaged.
    :param triage_bugzill_url: Link to a saved bugzilla search to follow along while triaging.
    :param dict team_mapping: A mapping of bugzilla identifiers to team member names. If
                              provided this will be used to specifically call on team members
                              who have been involved in a given bug.
    """

    triage = []
    triage.append("**MemShrink triage:** %s" % str(datetime.date.today()))

    if triage_bugzilla_url:
        triage.append(TRIAGE_URL_TEMPLATE % (triage_bugzilla_url, triage_bugzilla_url))

    if triage_header:
        triage.append(triage_header)

    # TODO(ER): possibly set stream=true in the get, and use r.content
    r = requests.get(triage_csv_url)
    triage_list = r.text
    #triage_list = MOCK_INPUT
    print triage_list
    reader = UnicodeDictReader(StringIO.StringIO(triage_list))
    #reader = UnicodeDictReader(StringIO.StringIO(r.content))

    result = sorted(reader, key=lambda d: int(d['Bug ID']))

    bz_names = set(team_mapping.iterkeys())

    triage.append("%d bugs to triage" % len(result))
    triage.append("")

    bugs = [x['Bug ID'] for x in result]
    from multiprocessing import Pool
    pool = Pool(processes=12)
    commentors_list = pool.map(get_commentors, bugs)

    for (row, commentors) in zip(result, commentors_list):
        row['Bug URL'] = SHORT_URL_FMT % row['Bug ID']
        triage.append("-   [%(Bug ID)s](%(Bug URL)s) - %(Product)s :: %(Component)s - %(Summary)s" % row)
        triage.append("    ")
        triage.append("    Votes:")
        triage.append("")

        # Create list of users who reported, commented, or are assigned the bug
        bug_users = commentors #get_commentors(row['Bug ID'])
        bug_users.update( (row['Assignee'], row['Reporter']) )

        team_members = bug_users & bz_names
        if team_members:
            nicks = [ team_mapping[x] for x in team_members ]
            triage.append("    %s, what do you think?" % ", ".join(nicks))
            triage.append("")

        triage.append("")

    return "\n".join(triage)

if __name__ == "__main__":
    triage = generate_triage_text(TRIAGE_CSV, TRIAGE_HEADER, TRIAGE_URL, MEMSHRINKERS)
    import markdown
    html = markdown.markdown(triage)
    with open("triage.html", "w") as f:
        f.write(html)
