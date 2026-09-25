# keykeep_psono — personal password vault (psono protocol) deployment
# Deploy: /srv/salt/keykeep_psono/init.sls on the Salt master.
# Apply to the ledningssystem minion (192.168.11.91).

{% set conf = pillar.get('keykeep_psono:odoo_conf', '/etc/odoo/odoo.conf') %}

# 1. Ensure the module path exists (repo /usr/share/odoo-keykeep/keykeep_psono).
keykeep-psono-module:
  file.directory:
    - name: /usr/share/odoo-keykeep/keykeep_psono
    - user: odoo
    - group: odoo
    - recurse: True

# 2. Optional: pin the server identity keys in odoo.conf (preferred over the
#    auto-generated keys file /var/lib/odoo/keykeep_psono_keys.conf).
#    If omitted, the module's post_init_hook generates a keypair on install
#    and writes it to /var/lib/odoo/keykeep_psono_keys.conf (mode 600).
#    BACK UP the keys file together with the database — losing it makes the
#    vault unreadable for clients (TOFU verify_key changes).
{% if pillar.get('keykeep_psono:private_key') and pillar.get('keykeep_psono:public_key') %}
keykeep-psono-keys:
  cmd.run:
    - name: |
        python3 - <<'PYEOF'
        conf = '{{ conf }}'
        with open(conf) as f:
            content = f.read()
        lines = {
            'keykeep_psono_private_key': '{{ pillar["keykeep_psono:private_key"] }}',
            'keykeep_psono_public_key': '{{ pillar["keykeep_psono:public_key"] }}',
        }
        changed = False
        with open(conf) as f:
            text = f.read()
        for k, v in lines.items():
            if ('%s =' % k) not in text:
                text += '\n%s = %s\n' % (k, v)
                changed = True
        if changed:
            with open(conf, 'w') as f:
                f.write(text)
            print('keys written')
        else:
            print('keys exist')
        PYEOF
    - unless: grep -q '^keykeep_psono_private_key' {{ conf }}
    - runas: root
{% endif %}

# 3. Install / upgrade the module (checkmodule handles service restart).
keykeep-psono-install:
  cmd.run:
    - name: checkmodule -d ledningssystem -m keykeep_psono
    - runas: root
    - onchanges:
        - file: keykeep-psono-module

# 4. Caddy rate_limit on auth endpoints (apply via caddy_site on the master).
#    Add to the ledningssystem Caddy site (/srv/salt/caddy/sites/ledningssystem.yml):
#
#      handle_path /keykeep/psono/authentication/prelogin* {
#          rate_limit {
#              zone dynamic {
#                  key {remote_host}
#                  events 10
#                  window 1m
#              }
#          }
#          reverse_proxy odoo-ledningssystem
#      }
#      handle_path /keykeep/psono/authentication/login* {
#          rate_limit {
#              zone dynamic {
#                  key {remote_host}
#                  events 10
#                  window 1m
#              }
#          }
#          reverse_proxy odoo-ledningssystem
#      }
#      handle_path /keykeep/psono/authentication/register* {
#          rate_limit {
#              zone dynamic {
#                  key {remote_host}
#                  events 5
#                  window 1m
#              }
#          }
#          reverse_proxy odoo-ledningssystem
#      }
#      handle /keykeep/psono/* {
#          reverse_proxy odoo-ledningssystem
#      }

# 5. Zabbix check (on the Zabbix server):
#    HTTP check: https://ledningssystem.vertel.se/keykeep/psono/info/ -> 200
#    Name: Odoo keykeep_psono /info/
#    Triggers: HTTP response code != 200 or no data
