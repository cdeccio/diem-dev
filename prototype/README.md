# Prototype



# Examples

## [UNESCO World Heritage Convention](https://whc.unesco.org/)
 - [World Heritage List](https://whc.unesco.org/en/list/)
 - Data: [RSS Feed](https://whc.unesco.org/en/list/rss/)
 - Digital emblem control:
   - Settings:
     - Name template: `_diem.<id>.unesco.examples.prototype.digitalemblem.org`
     - Zone: `unesco.examples.prototype.digitalemblem.org`
   - Provisioning:
     ```
     ./importdb_unesco.py --output_file unesco.jsonl unesco-sites.xml unesco unesco.examples.prototype.digitalemblem.org
     ./createjwt.py --human_readable --update_dns --subzone_labels 2 unesco.jsonl 
     ```
   - Retrieval:
     ```
     dig _diem.129.unesco.examples.prototype.digitalemblem.org txt
     dig _diem.h.129.unesco.examples.prototype.digitalemblem.org txt
     ```

## [The Convention on Wetlands](https://ramsar.org/)
 - [List of Wetlands of International Importance (aka the Ramsar List)](https://rsis.ramsar.org/#list)
 - Data: [Email export](https://rsis.ramsar.org/#exports)
 - Digital emblem control:
   - Settings:
     - Name template: `_diem.<id>.ramsar.examples.prototype.digitalemblem.org`
     - Zone: `ramsar.examples.prototype.digitalemblem.org`
   - Provisioning:
     ```
     ./importdb_ramsar.py --output_file ramsar.jsonl ris.csv ramsar ramsar.examples.prototype.digitalemblem.org
     ./createjwt.py --human_readable --update_dns --subzone_labels 2 ramsar.jsonl 
     ```
   - Retrieval:
     ```
     dig _diem.813.ramsar.examples.prototype.digitalemblem.org txt
     dig _diem.h.813.ramsar.examples.prototype.digitalemblem.org txt
     ```

## (International Committee of the Red Cross)[https://www.icrc.org/]
   - Data: [RIPE Whois](https://apps.db.ripe.net/db-web-ui/query?bflag=false&dflag=false&rflag=true&searchtext=80.94.146.0&source=RIPE)
   - Settings:
     - Name template (IP): `_diem.<asn>.asn.swisscom.examples.prototype.digitalemblem.org`
     - Name template (ASN): `_diem.<reversed_octets_minimized>.<prefix_len>.<ip_or_ip6>.icrc.examples.prototype.digitalemblem.org`
   - Provisioning:
     ```
     ./importdb_ip.py --output_file ipinfo.jsonl ipinfo.csv icrc icrc.examples.prototype.digitalemblem.org
     ./importdb_asn.py --output_file asinfo.jsonl asinfo.csv swisscom swisscom.examples.prototype.digitalemblem.org
     ```
