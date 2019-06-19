#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2019, OVH SAS
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}


DOCUMENTATION = '''
---
module: zabbix_user
short_description: Create/update/delete/dump Zabbix user
description:
    - Create/update/delete/dump Zabbix user.
version_added: "2.9"
author:
    - Emmanuel Riviere (@emriver)
requirements:
    - "python >= 2.7"
    - "zabbix-api >= 0.5.3"
options:
    alias:
        description:
            - Zabbix user alias
        type: str
        required: true
    name:
        description:
            - Zabbix user name
        type: str
        required: false
    surname:
        description:
            - Zabbix user surname
        type: str
        required: false
    password:
        description:
            - Zabbix user password
        type: str
        required: false
    update_password:
        description:
            - Always will update passwords if they differ.
            - On_create will only set the password for newly created users.
        type: str
        choices: [ always, on_create ]
        default: always
    user_type:
        description:
            - Zabbix user type
        required: false
        choices: [user, admin, super_admin]
        default: user
    autologin:
        description:
            - Enable or not autologin
        required: false
        type: bool
        default: false
    autologout:
        description:
            - Time before auto logout
        required: false
        type: str
        default: 15m
    lang:
        description:
            - Zabbix web UI language
        required: false
        type: str
        default: en_GB
    refresh:
        description:
            - UI refresh rate
        required: false
        type: str
        default: 30s
    rows_per_page:
        description:
            - Number of rows displayed per page
        required: false
        type: int
        default: 50
    theme:
        description:
            - Zabbix front-end theme
        required: false
        choices: [default, blue-theme, dark-theme]
        default: default
    groups:
        description:
            - list of user groups
        required: false
    state:
        description:
            - Present: create/update user, absent: delete user, dump: dump user data
        required: false
        choices: [present, absent, dump]
        default present
    media:
        description:
            - List of medias (see example below)
            - 'Available keys are: I(active), I(period), I(media_type), I(send_to), I(severity) '
            - 'https://www.zabbix.com/documentation/4.0/manual/api/reference/user/object#media'
        required: false
        default: []
extends_documentation_fragment:
    - zabbix
'''

EXAMPLES = '''
---
- name: Dump Zabbix user group info
  local_action:
    module: zabbix_user_group
    server_url: http://127.0.0.1
    login_user: username
    login_password: password
    alias: test
    state: dump

- name: Create test user
  local_action:
    module: zabbix_user_group
    server_url: http://127.0.0.1
    login_user: username
    login_password: password
    state: present
    alias: test
    password: 1234test!
    user_type: user
    groups:
        - readonly
    medias:
        - media_type: Email
          active: true
          severity: 63
          send_to: user@mail.com
          period: "1-7, 00:00-24:00"
'''

RETURN = '''
---
template_json:
  description: The JSON dump of the user
  returned: when state is dump
  type: str
  sample: {
    "user_json": {
        "alias": "test",
        "attempt_clock": "0",
        "attempt_failed": "0",
        "attempt_ip": "",
        "autologin": "0",
        "autologout": "15m",
        "lang": "en_GB",
        "medias": [
            {
                "active": "0",
                "mediaid": "8",
                "mediatypeid": "1",
                "period": "1-7,00:00-24:00",
                "sendto": [
                    "user@mail.com"
                ],
                "severity": "63",
                "userid": "12"
            }
        ],
        "name": "",
        "refresh": "30s",
        "rows_per_page": "50",
        "surname": "",
        "theme": "default",
        "type": "1",
        "url": "",
        "userid": "12",
        "usrgrps": [
            {
                "usrgrpid": "19"
            }
        ]
    }
  }
'''

from distutils.version import LooseVersion
from ansible.module_utils.basic import AnsibleModule

try:
    from zabbix_api import ZabbixAPI, ZabbixAPIException

    HAS_ZABBIX_API = True
except ImportError:
    HAS_ZABBIX_API = False


class User(object):
    def __init__(self, module, zbx):
        self._module = module
        self._zapi = zbx

    def get_id(self, alias):
        user_id = None
        users = self._zapi.user.get({'filter':{'alias':alias}})

        if len(users) == 1:
            user_id = users[0]['userid']
        return user_id

    def delete(self, user_id):
        if self._module.check_mode:
            self._module.exit_json(changed=True)
        self._zapi.user.delete([user_id])

    def dump(self, user_id):
        users = self._zapi.user.get({'output': 'extend', 'selectMedias':'extend', 'selectUsrgrps':1, 'userids':user_id})
        return users[0]

    def generate_config(self, alias, name, surname, password, user_type, groups, medias, autologin, autologout, lang, refresh, rows_per_page, theme):
        if autologin:
            autologin = "1"
        else:
            autologin = "0"

        user_types = {'user': '1', 'admin': '2', 'super_admin': '3'}
        user_type = user_types[user_type]

        api_groups = []
        for group in groups:
            groups = self._zapi.usergroup.get({'filter': {'name': group}})
            if not groups:
                self._module.fail_json(msg="Target user group %s not found" % group)
            group_id = groups[0]['usrgrpid']
            api_groups.append({'usrgrpid':group_id})

        api_medias = []
        for media in medias:
            media_types = self._zapi.mediatype.get({'filter': {'description': media['media_type']}})
            if not media_types:
                self._module.fail_json(msg="Target media type %s not found" % media['media_type'])
            media_type_id = media_types[0]['mediatypeid']

            active = "1"
            if media['active']:
                active = "0"

            api_medias.append({
                'mediatypeid': media_type_id,
                'sendto': media['send_to'],
                'active': active,
                'severity': media['severity'],
                'period': media['period']
            })

        request = {
            'alias': alias,
            'autologin': autologin,
            'autologout': autologout,
            'lang': lang,
            'name': name,
            'refresh': refresh,
            'rows_per_page': str(rows_per_page),
            'surname': surname,
            'theme': theme,
            'type': user_type,
            'user_medias': api_medias,
            'usrgrps': api_groups
        }

        if password != None:
            request['passwd'] = password

        return request

    def compare_config(self, generated, current):
        items_to_check = ['alias', 'autologin', 'autologout', 'lang', 'name', 'refresh', 'rows_per_page', 'surname', 'theme', 'type']
        for item in items_to_check:
            if str(generated[item]) != str(current[item]):
                return True

        if [group['usrgrpid'] for group in generated['usrgrps']] != [group['usrgrpid'] for group in current['usrgrps']]:
            return True

        new_gmedia = []
        for media in generated['user_medias']:
            new_gmedia.append(media['mediatypeid']+media['severity']+media['period']+media['active']+''.join(media['sendto']))

        new_cmedia = []
        for media in current['medias']:
            new_cmedia.append(media['mediatypeid']+media['severity']+media['period']+media['active']+''.join(media['sendto']))

        if set(new_gmedia) != set(new_cmedia):
            return True

        if 'passwd' in generated:
            return self.check_diff_password(generated['alias'], generated['passwd'])

        return False

    def check_diff_password(self, user, password):
        try:
            self._zapi.login(user, password, False)
        except ZabbixAPIException as error:
            #error code for auth failed
            if '32500' in str(error):
                return True
            self._module.fail_json(msg="Failed to connect to Zabbix server: %s" % error)
        #auth again with right credentials
        self._zapi.login()
        return False

    def create(self, alias, name, surname, password, user_type, groups, medias, autologin, autologout, lang, refresh, rows_per_page, theme):
        if self._module.check_mode:
            self._module.exit_json(changed=True)
        self._zapi.user.create(self.generate_config(alias, name, surname, password, user_type, groups, medias, autologin, autologout, lang, refresh, rows_per_page, theme))

    def update(self, user_id, alias, name, surname, password, user_type, groups, medias, autologin, autologout, lang, refresh, rows_per_page, theme):
        current_config = self.dump(user_id)
        generated_config = self.generate_config(alias, name, surname, password, user_type, groups, medias, autologin, autologout, lang, refresh, rows_per_page, theme)

        changed = self.compare_config(generated_config, current_config)

        if self._module.check_mode:
            self._module.exit_json(changed=changed)

        if changed:
            generated_config['userid'] = user_id
            self._zapi.user.update(generated_config)

        return changed

def main():
    module = AnsibleModule(
        argument_spec=dict(
            server_url=dict(type='str', required=True, aliases=['url']),
            login_user=dict(type='str', required=True),
            login_password=dict(type='str', required=True, no_log=True),
            http_login_user=dict(type='str', required=False, default=None),
            http_login_password=dict(type='str', required=False, default=None, no_log=True),
            validate_certs=dict(type='bool', required=False, default=True),
            alias=dict(type='str', required=True),
            name=dict(type='str', default='', required=False),
            surname=dict(type='str', default='', required=False),
            password=dict(type='str', no_log=True),
            update_password=dict(type='str', default='always', choices=['always', 'on_create']),
            user_type=dict(type='str', default='user', required=False, choices=['user', 'admin', 'super_admin']),
            groups=dict(type='list', required=False, elements='str'),
            medias=dict(
                type='list',
                elements='dict',
                required=False,
                default=[],
                options=dict(
                    media_type=dict(type='str', required=True),
                    active=dict(type='bool', required=False, default=True),
                    severity=dict(type='str', required=False, default="63"),
                    period=dict(type='str', required=False, default='1-7,00:00-24:00'),
                    send_to=dict(type='list', required=True, elements='str')
                )
            ),
            autologin=dict(type='bool', default=False, required=False),
            autologout=dict(type='str', default='15m', required=False),
            lang=dict(type='str', default='en_GB', required=False),
            refresh=dict(type='str', default='30s', required=False),
            rows_per_page=dict(type='int', default=50, required=False),
            theme=dict(default='default', required=False, choices=['default', 'blue-theme', 'dark-theme']),
            state=dict(default="present", required=False, choices=['present', 'absent', 'dump']),
            timeout=dict(type='int', default=10)
        ),
        supports_check_mode=True
    )

    if not HAS_ZABBIX_API:
        module.fail_json(msg="Missing required zabbix-api module " +
                         "(check docs or install with: " +
                         "pip install zabbix-api)")

    server_url = module.params['server_url']
    login_user = module.params['login_user']
    login_password = module.params['login_password']
    http_login_user = module.params['http_login_user']
    http_login_password = module.params['http_login_password']
    validate_certs = module.params['validate_certs']
    alias = module.params['alias']
    name = module.params['name']
    surname = module.params['surname']
    password = module.params['password']
    update_password = module.params['update_password']
    user_type = module.params['user_type']
    groups = module.params['groups']
    medias = module.params['medias']
    autologin = module.params['autologin']
    autologout = module.params['autologout']
    lang = module.params['lang']
    refresh = module.params['refresh']
    rows_per_page = module.params['rows_per_page']
    theme = module.params['theme']
    state = module.params['state']
    timeout = module.params['timeout']

    zbx = None

    #login to zabbix
    try:
        zbx = ZabbixAPI(server_url, timeout=timeout, user=http_login_user, passwd=http_login_password, validate_certs=validate_certs)
        zbx.login(login_user, login_password)
    except ZabbixAPIException as error:
        module.fail_json(msg="Failed to connect to Zabbix server: %s" % error)

    #load UserGroup module
    user = User(module, zbx)
    user_id = user.get_id(alias)

    #delete group
    if state == "absent":
        if not user_id:
            module.exit_json(changed=False, msg="User not found, no change: %s" % alias)
        user.delete(user_id)
        module.exit_json(changed=True, result="Successfully deleted user %s" % alias)

    elif state == "dump":
        if not user_id:
            module.fail_json(msg='User not found: %s' % alias)
        module.exit_json(changed=False, user_json=user.dump(user_id))

    elif state == "present":
        #Does not exists going to create it
        if not groups:
            module.fail_json(msg="Missing argument groups to create user %s" % alias)
        if not user_id:
            if password == '':
                module.fail_json(msg="Missing argument password to create user %s" % alias)
            user.create(alias, name, surname, password, user_type, groups, medias, autologin, autologout, lang, refresh, rows_per_page, theme)
            module.exit_json(changed=True, msg="User %s created" % alias)
        #Else we update it
        else:
            if update_password == 'always' and password == '':
                module.fail_json(msg="Missing argument password to update user %s" % alias)
            elif update_password == 'on_create':
                password = None
            changed = user.update(user_id, alias, name, surname, password, user_type, groups, medias, autologin, autologout, lang, refresh, rows_per_page, theme)
            module.exit_json(changed=changed)

if __name__ == '__main__':
    main()
