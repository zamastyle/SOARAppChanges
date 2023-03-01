import sys
import requests
import json
import re
import datetime

requests.packages.urllib3.disable_warnings()


### Static Vars
CLEANER = re.compile('<.*?>')
TAGS = ['<p>', '</p>', '<span>', '</span>', '</li>']
PRIVATE_SLACK = '<private slack webhook>'
COMMUNITY_SLACK = '<community slack webhook>'


### Send message to slack channels
def slack(message):
  message = {"text": message}
  response = requests.post(PRIVATE_SLACK, data=json.dumps(message), verify=False)
  print(response)
  response = requests.post(COMMUNITY_SLACK, data=json.dumps(message), verify=False)
  print(response)


### Clean out extra HTML content in the body
def cleanhtml(raw_html):
  # Clean troublesome tags first
  raw_html = raw_html.replace('\n', ' ')
  for tag in TAGS:
    raw_html = raw_html.replace(tag, '')
  # Bullet placeholder until html is cleaned up
  raw_html = raw_html.replace('<li>', '-----')
  while '  ' in raw_html:
    raw_html = raw_html.replace('  ', ' ')
  # Remove the remaining tags aggressively
  cleantext = re.sub(CLEANER, '', raw_html)
  # Replace bullet placeholder with bullet
  cleantext = cleantext.replace('-----', '\n  - ')
  return cleantext


### Retrieve app details by splunkbase ID
def get_app_info(sbid):
  print('Getting app details for app id {}'.format(sbid))
  html_response = requests.get('https://splunkbase.splunk.com/app/{0}/'.format(sbid))
  html_data = html_response.text
  action_data = html_data[html_data.index('Supported Actions Version'):]
  action_data = action_data[:action_data.index('</sb-release-select>')]
  action_data = cleanhtml(action_data)
  change_data = html_data[html_data.index('Release Notes'):]
  change_data = change_data[:change_data.index('</sb-release-select>')]
  change_data = cleanhtml(change_data)
  return action_data, change_data


### Print date to log for context
print( '\n' + str(datetime.datetime.now()) )

### Build New App Lookup From Repo Data
app_lookup = {}
page = 0
total = 0
while True:
  url = ('https://splunkbase.splunk.com/api/v2/apps/'
        f'?offset={page}'
         '&limit=20'
         '&archive=false'
         '&product=soar'
         '&include=release,release.version_compatibility')
  response = requests.get(url)
  if total == 0:
    total = json.loads(response.text)['total']
  for app_pkg in json.loads(response.text)['results']:
    package_data = {}
    package_data['name'] = app_pkg['app_name']
    package_data['description'] = app_pkg['description']
    package_data['app_id'] = app_pkg['app_id']
    package_data['sbid'] = app_pkg['id']
    package_data['version'] = app_pkg['release']['release_name']
    package_data['compatible_with'] = app_pkg['release']['version_compatibility']
    package_data['changes'] = 'Change Log:{}'.format(cleanhtml(app_pkg['release']['notes']))
    app_lookup[package_data['app_id']] = package_data
  page += 20
  if page > total:
    break

### Get app cache from local file
app_cache = None
try:
  file = open("./app_cache","r+")
  app_cache = json.loads(file.read())
except:
  file = open("./app_cache","w+")
  file.write(json.dumps(app_lookup))
  file.close()
  sys.exit(0)

### Identify new content between current splunkbase and cache
new = []
updated = []
for entry in app_lookup:
  if entry not in app_cache:
      print(f'New app released: {app_lookup[entry]["name"]}')
      new.append((f'> New app available: *{app_lookup[entry]["name"]}*\n'
                  f' Compatible with: {", ".join(app_lookup[entry]["compatible_with"])}\n'
                  f'```{app_lookup[entry]["changes"]}```\n\n'))
  elif app_lookup[entry]['version'] != app_cache[entry]['version']:
      print(f'{app_lookup[entry]["name"]} updated from {app_cache[entry]["version"]} to {app_lookup[entry]["version"]}')
      updated.append((f'> Updated app: *{app_lookup[entry]["name"]}*\n'
                      f'> {app_lookup[entry]["name"]} v{app_lookup[entry]["version"]}\n'
                      f'> Compatible with: {", ".join(app_lookup[entry]["compatible_with"])}\n'
                      f'```{app_lookup[entry]["changes"]}```\n\n'))

### Write out new app cache to file
try:
  file = open("./app_cache","w+")
  file.write(json.dumps(app_lookup))
  file.close()
except:
  pass

### Post update messages to slack
if not new and not updated:
  print("No new or updated apps")
else:
  for entry in new:
    slack(entry)
  for entry in updated:
    slack(entry)
