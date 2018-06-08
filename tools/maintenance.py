"""
    Runs a series of maintenance operations on the collection of entry files, updating the table of content files for
    each category as well as creating a statistics file.

    Counts the number of records each sub-folder and updates the overview.
    Sorts the entries in the contents files of each sub folder alphabetically.

    This script runs with Python 3, it could also with Python 2 with some minor tweaks probably.
"""

import os
import re
import urllib.request
import http.client
import datetime
import json

TOC = '_toc.md'


def read_text(file):
    """
    Reads a whole text file (UTF-8 encoded).
    """
    with open(file, mode='r', encoding='utf-8') as f:
        text = f.read()
    return text


def read_first_line(file):
    """
    Convenience function because we only need the first line of a category overview really.
    """
    with open(file, mode='r', encoding='utf-8') as f:
        line = f.readline()
    return line


def write_text(file, text):
    """
    Writes a whole text file (UTF-8 encoded).
    """
    with open(file, mode='w', encoding='utf-8') as f:
        f.write(text)


def get_category_paths():
    """
    Returns all sub folders of the games path.
    """
    return [os.path.join(games_path, x) for x in os.listdir(games_path) if os.path.isdir(os.path.join(games_path, x))]


def get_entry_paths(category_path):
    """
    Returns all files of a category path, except for '_toc.md'.
    """
    return [os.path.join(category_path, x) for x in os.listdir(category_path) if x != TOC and os.path.isfile(os.path.join(category_path, x))]


def extract_overview_for_toc(file):
    """
    Parses a file for some interesting fields and concatenates the content.
    
    To be displayed after the game name in the category TOCs.
    """
    with open(file, mode='r', encoding='utf-8') as f:
        text = f.read()

    info = parse_entry(text)

    output = []

    if 'code language' in info:
        output.extend(info['code language'])

    if 'code license' in info:
        output.extend(info['code license'])

    # state
    if 'state' in info:
        output.extend(info['state'])

    output = ", ".join(output)

    return output


def update_readme():
    """
    Recounts entries in sub categories and writes them to the readme.
    Also updates the _toc files in the categories directories.

    Note: The Readme must have a specific structure at the beginning, starting with "# Open Source Games" and ending
    on "A collection.."

    Needs to be performed regularly.
    """
    print('update readme file')

    # read readme
    readme_text = read_text(readme_file)

    # compile regex for identifying the building blocks
    regex = re.compile(r"(# Open Source Games\n\n)(.*)(\nA collection.*)", re.DOTALL)

    # apply regex
    matches = regex.findall(readme_text)
    assert len(matches) == 1
    matches = matches[0]
    start = matches[0]
    end = matches[2]

    # get sub folders
    category_paths = get_category_paths()

    # assemble paths
    toc_paths = [os.path.join(path, TOC) for path in category_paths]

    # get titles (discarding first two ("# ") and last ("\n") characters)
    category_titles = [read_first_line(path)[2:-1] for path in toc_paths]

    # get number of files (minus 1 for the already existing TOC file) in each sub folder
    n_entries = [len(os.listdir(path)) - 1 for path in category_paths]

    # combine titles, category names, numbers in one list
    info = zip(category_titles, [os.path.basename(path) for path in category_paths], n_entries)

    # sort according to sub category title (should be unique)
    info = sorted(info, key=lambda x:x[0])

    # assemble output
    update = ['- **[{}](games/{}/{})** ({})\n'.format(entry[0], entry[1], TOC, entry[2]) for entry in info]
    update = "{} entries\n".format(sum(n_entries)) + "".join(update)

    # insert new text in the middle
    text = start + "[comment]: # (start of autogenerated content, do not edit)\n" + update + "\n[comment]: # (end of autogenerated content)" + end

    # write to readme
    write_text(readme_file, text)


def update_category_tocs():
    """
    Lists all entries in all sub folders and generates the list in the toc file.

    Needs to be performed regularly.
    """
    # get category paths
    category_paths = get_category_paths()

    # for each category
    for category_path in category_paths:
        print('generate toc for {}'.format(os.path.basename(category_path)))

        # read toc header line
        toc_file = os.path.join(category_path, TOC)
        toc_header = read_first_line(toc_file) # stays as is

        # get paths of all entries in this category
        entry_paths = get_entry_paths(category_path)

        # get titles (discarding first two ("# ") and last ("\n") characters)
        titles = [read_first_line(path)[2:-1] for path in entry_paths]

        # get more interesting info
        more = [extract_overview_for_toc(path) for path in entry_paths]

        # combine name, file name and more info
        info = zip(titles, [os.path.basename(path) for path in entry_paths], more)

        # sort according to entry title (should be unique)
        info = sorted(info, key=lambda x:x[0])

        # assemble output
        update = ['- **[{}]({})** ({})\n'.format(*entry) for entry in info]
        update = "".join(update)

        # combine with toc header
        text = toc_header + '\n' + "[comment]: # (start of autogenerated content, do not edit)\n" + update + "\n[comment]: # (end of autogenerated content)"

        # write to toc file
        with open(toc_file, mode='w', encoding='utf-8') as f:
            f.write(text)


def check_validity_external_links():
    """
    Checks all external links it can find for validity. Prints those with non OK HTTP responses. Does only need to be run
    from time to time.
    """
    # regex for finding urls (can be in <> or in () or a whitespace
    regex = re.compile(r"[\s\n]<(http.+?)>|\]\((http.+?)\)|[\s\n](http[^\s\n]+)")

    # count
    number_checked_links = 0

    # get category paths
    category_paths = get_category_paths()

    # for each category
    for category_path in category_paths:
        print('check links for {}'.format(os.path.basename(category_path)))

        # get entry paths
        entry_paths = get_entry_paths(category_path)

        # for each entry
        for entry_path in entry_paths:
            # read entry
            with open(entry_path, 'r', 'utf-8') as f:
                content = f.read()

            # apply regex
            matches = regex.findall(content)

            # for each match
            for match in matches:

                # for each possible clause
                for url in match:

                    # if there was something
                    if url:
                        try:
                            # without a special headers, frequent 403 responses occur
                            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64)'})
                            urllib.request.urlopen(req)
                        except urllib.error.HTTPError as e:
                            print("{}: {} - {}".format(os.path.basename(entry_path), url, e.code))
                        except http.client.RemoteDisconnected:
                            print("{}: {} - disconnected without response".format(os.path.basename(entry_path), url))

                        number_checked_links += 1

                        if number_checked_links % 50 == 0:
                            print("{} links checked".format(number_checked_links))

    print("{} links checked".format(number_checked_links))


def check_template_leftovers():
    """
    Checks for template leftovers.

    Should be run only occasionally.
    """

    # load template and get all lines
    text = read_text(os.path.join(games_path, 'template.md'))
    text = text.split('\n')
    check_strings = [x for x in text if x and not x.startswith('##')]

    # get category paths
    category_paths = get_category_paths()

    # for each category
    for category_path in category_paths:
        # get paths of all entries in this category
        entry_paths = get_entry_paths(category_path)

        for entry_path in entry_paths:
            # read it line by line
            content = read_text(entry_path)

            for check_string in check_strings:
                if content.find(check_string) >= 0:
                    print('{}: found {}'.format(os.path.basename(entry_path), check_string))


def parse_entry(content):
    """
    Returns a dictionary of the features of the content
    """

    info = {}

    # read title
    regex = re.compile(r"^# (.*)")
    matches = regex.findall(content)
    assert len(matches) == 1
    info['title'] = matches[0]

    # first read all field names
    regex = re.compile(r"^- (.*?): ", re.MULTILINE)
    fields = regex.findall(content)

    # iterate over found field
    for field in fields:
        regex = re.compile(r"- {}: (.*)".format(field))
        matches = regex.findall(content)
        assert len(matches) == 1 # every field should only be present once
        v = matches[0]

        # first store as is
        info[field.lower()+'-raw'] = v

        # remove parenthesis
        v = re.sub(r'\([^)]*\)', '', v)

        # split on ','
        v = v.split(',')

        # finally strip
        v = [x.strip() for x in v]

        # store in info
        info[field.lower()] = v

    # checks

    # essential fields
    essential_fields = ['home', 'state']
    for field in essential_fields:
        if field not in info:
            print('Essential field "{}" missing in entry {}'.format(field, info['title']))
            return info # so that the rest can run through

    # state must contain either beta or mature but not both
    v = info['state']
    if 'beta' in v != 'mature' in v:
        printf('State must be one of <beta, mature> in entry {}'.format(info['title']))
        return info # so that the rest can run through

    # extract inactive
    phrase = 'inactive since '
    inactive_year = [x[len(phrase):] for x in info['state'] if x.startswith(phrase)]
    if inactive_year:
        info['inactive'] = inactive_year

    return info


def assemble_infos():
    """
    Parses all entries and assembles interesting infos about them.
    """
    # get category paths
    category_paths = get_category_paths()

    # a database of all important infos about the entries
    infos = []

    # for each category
    for category_path in category_paths:
        # get paths of all entries in this category
        entry_paths = get_entry_paths(category_path)

        # get titles (discarding first two ("# ") and last ("\n") characters)
        category = read_first_line(os.path.join(category_path, TOC))[2:-1]

        for entry_path in entry_paths:
            # read entry
            content = read_text(entry_path)

            # parse entry
            info = parse_entry(content)

            # add category
            info['category'] = category

            # add file information
            info['file'] = os.path.basename(entry_path)[:-3] # [:-3] to cut off the .md

            # add to list
            infos.append(info)

    return infos

def generate_statistics():
    """
    Generates the statistics page.

    Should be done every time the entries change.
    """

    # start the page
    statistics_path = os.path.join(games_path, 'statistics.md')
    statistics = '[comment]: # (autogenerated content, do not edit)\n# Statistics\n\n'

    # assemble infos
    infos = assemble_infos()

    # total number
    number_entries = len(infos)
    rel = lambda x: x / number_entries * 100 # conversion to percent
    statistics += 'analyzed {} entries on {}\n\n'.format(number_entries, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    # State (beta, mature, inactive)
    statistics += '## State\n\n'

    number_state_beta = sum(1 for x in infos if 'beta' in x['state'])
    number_state_mature = sum(1 for x in infos if 'mature' in x['state'])
    number_inactive = sum(1 for x in infos if 'inactive' in x)
    statistics += '- mature: {} ({:.1f}%)\n- beta: {} ({:.1f}%)\n- inactive: {} ({:.1f}%)\n\n'.format(number_state_mature, rel(number_state_mature), number_state_beta, rel(number_state_beta), number_inactive, rel(number_inactive))

    if number_inactive > 0:
        entries_inactive = [(x['file'], x['inactive']) for x in infos if 'inactive' in x]
        entries_inactive.sort(key=lambda x: x[0])  # first sort by name
        entries_inactive.sort(key=lambda x: -x[1]) # then sort by inactive year (more recently first)
        entries_inactive = ['{} ({})'.format(*x) for x in entries_inactive]
        statistics += '##### Inactive State\n\n' + ', '.join(entries_inactive) + '\n\n'

    entries_no_state = [x['file'] for x in infos if 'state' not in x]
    if entries_no_state:
        entries_no_state.sort()
        statistics += '##### Without state tag ({})\n\n'.format(len(entries_no_state)) + ', '.join(entries_no_state) + '\n\n'

    # Language
    statistics += '## Languages\n\n'
    number_no_language = sum(1 for x in infos if 'language' not in x)
    if number_no_language > 0:
        statistics += 'Without language tag: {} ({:.1f}%)\n\n'.format(number_no_language, rel(number_no_language))
        entries_no_language = [x['file'] for x in infos if 'language' not in x]
        entries_no_language.sort()
        statistics += ', '.join(entries_no_language) + '\n\n'

    # get all languages together
    languages = []
    for info in infos:
        if 'language' in info:
            languages.extend(info['language'])

    unique_languages = set(languages)
    unique_languages = [(l, languages.count(l) / len(languages)) for l in unique_languages]
    unique_languages.sort(key=lambda x: x[0]) # first sort by name
    unique_languages.sort(key=lambda x: -x[1]) # then sort by occurrence (highest occurrence first)
    unique_languages = ['- {} ({:.1f}%)\n'.format(x[0], x[1]*100) for x in unique_languages]
    statistics += '##### Language frequency\n\n' + ''.join(unique_languages) + '\n'

    # Licenses
    statistics += '## Code licenses\n\n'
    number_no_license = sum(1 for x in infos if 'license' not in x)
    if number_no_license > 0:
        statistics += 'Without license tag: {} ({:.1f}%)\n\n'.format(number_no_license, rel(number_no_license))
        entries_no_license = [x['file'] for x in infos if 'license' not in x]
        entries_no_license.sort()
        statistics += ', '.join(entries_no_license) + '\n\n'

    # get all licenses together
    licenses = []
    for info in infos:
        if 'license' in info:
            licenses.append(info['license'])

    unique_licenses = set(licenses)
    unique_licenses = [(l, licenses.count(l) / len(licenses)) for l in unique_licenses]
    unique_licenses.sort(key=lambda x: x[0]) # first sort by name
    unique_licenses.sort(key=lambda x: -x[1]) # then sort by occurrence (highest occurrence first)
    unique_licenses = ['- {} ({:.1f}%)\n'.format(x[0], x[1]*100) for x in unique_licenses]
    statistics += '##### Licenses frequency\n\n' + ''.join(unique_licenses) + '\n'

    with open(statistics_path, mode='w', encoding='utf-8') as f:
        f.write(statistics)


def export_json():
    """
    Parses all entries, collects interesting info and stores it in a json file suitable for displaying
    with a dynamic table in a browser.
    """

    # assemble info
    infos = assemble_infos()

    # make database out of it
    db = {}
    db['headings'] = ['Name', 'Download']

    entries = []
    for info in infos:
        entry = [info['title']]
        if 'download' in info:
            entry.append(info['download'][0])
        else:
            entry.append('')
        entries.append(entry)
    db['data'] = entries

    # output
    json_path = os.path.join(games_path, os.path.pardir, 'docs', 'data.json')
    text = json.dumps(db)
    write_text(json_path, text)


if __name__ == "__main__":

    # paths
    games_path = os.path.realpath(os.path.join(os.path.dirname(__file__), os.path.pardir, 'games'))
    readme_file = os.path.realpath(os.path.join(games_path, os.pardir, 'README.md'))

    # recount and write to readme
    #update_readme()

    # generate list in toc files
    #update_category_tocs()

    # generate report
    #generate_statistics()

    # update database for html table
    export_json()

    # check for unfilled template lines
    # check_template_leftovers()

    # check external links (only rarely)
    # check_validity_external_links()
