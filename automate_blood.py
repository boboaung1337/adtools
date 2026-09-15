#!/usr/local/bin/python3
# CREATOR: PatxaSec

import json
import zipfile
import sys
import os
import argparse

def parse_json(zip_path):
    sid_map = {}
    relaciones = []
    conteo_por_tipo = {}

    with zipfile.ZipFile(zip_path, 'r') as z:
        json_files = [f for f in z.namelist() if f.endswith('.json')]

        if not json_files:
            print("[ERROR] No JSON files found in the ZIP.")
            return sid_map, relaciones, conteo_por_tipo

        for file in json_files:
            with z.open(file) as f:
                content = json.load(f)
                objs = content.get("data", [])
                meta = content.get("meta", {})
                general_type = meta.get("type", "Unknown").lower()
                count = meta.get("count", 0)

                # Acumular conteo por tipo desde meta.count
                conteo_por_tipo[general_type] = conteo_por_tipo.get(general_type, 0) + count

                for obj in objs:
                    sid = obj.get("ObjectIdentifier", None)
                    if sid:
                        entity_type = obj.get("type", general_type)
                        obj["_tipo"] = entity_type
                        sid_map[sid] = obj
                        if "Aces" in obj:
                            for ace in obj["Aces"]:
                                right = ace.get("RightName", "")
                                if right in (
                                        "AdminTo", "GenericAll", "GenericWrite", "WriteOwner", "WriteDacl", "WriteProperty",
                                        "ReadProperty", "ExtendedRight", "AllExtendedRights", "ForceChangePassword", "ChangePassword",
                                        "ResetPassword", "WriteAccountRestrictions", "AddMember", "MemberOf", "Owns", "Contains",
                                        "AllowedToDelegate", "AllowedToAct", "HasSession", "CanRDP", "ExecuteDCOM", "AllowedToSync",
                                        "AddSelf", "RemoveSelf", "ReadLAPSPassword", "ReadGMSAPassword", "DCSync", "GetChanges",
                                        "GetChangesAll", "ManageGroup", "ShadowCredential", "UserRights", "Self", "ReadMembers",
                                        "AddMembers", "GenericRead", "GenericExecute", "Write", "Add", "Remove", "SyncLAPSAccount"
                                 ):
                                    origin_name = obj.get("Properties", {}).get("name", "Unknown")
                                    dest_sid = ace.get("PrincipalSID", "Unknown")
                                    dest_type = ace.get("PrincipalType", "Unknown")
                                    relaciones.append({
                                        "origen_sid": sid,
                                        "origen_nombre": origin_name,
                                        "origen_tipo": entity_type,
                                        "derecho": right,
                                        "destino_sid": dest_sid,
                                        "destino_tipo": dest_type
                                    })

    return sid_map, relaciones, conteo_por_tipo


def is_admin(entity):
    return entity.get("Properties", {}).get("admincount") == True

def is_kerberoastable(entity):
    props = entity.get("Properties", {})
    return props.get("hasspn", False)

def is_asrep_roastable(entity):
    props = entity.get("Properties", {})
    return props.get("trustedtoauth", False) and not props.get("userpassword", None)

def is_disabled(entity):
    props = entity.get("Properties", {})
    return not props.get("enabled", True)

def pwd_never_expires(entity):
    props = entity.get("Properties", {})
    return props.get("pwdneverexpires", False)

def is_old_os(entity):
    props = entity.get("Properties", {})
    os_name = props.get("operatingsystem")

    if not os_name:
        return False

    os_name = str(os_name).lower()

    deprecated_keywords = [
        "windows xp", "windows vista", "windows 7", "windows 8", "windows 8.1",
        "windows embedded standard", "windows embedded 8", "windows embedded 8.1",
        "windows server 2003", "windows server 2008", "windows server® 2008",
        "windows server 2012", "windows server 2012 r2"
    ]

    return any(keyword in os_name for keyword in deprecated_keywords)

def get_display_items(items, limit):
    if limit == ':':
        return items
    else:
        return items[:int(limit)]

def main():
    parser = argparse.ArgumentParser(description="Process BloodHound ZIP files and analyze relationships.")
    parser.add_argument('zip_path', help='Path to BloodHound ZIP file')
    parser.add_argument('limit', nargs='?', default=':', help="Limit number of displayed items per category (integer or ':')")
    parser.add_argument('-f', '--filter', default=None, help='Filter string for users/computers/groups/containers/OUs/domains/GPOs/rights')
    parser.add_argument('-a', '--filter-admin', action='store_true', help='Exclude relationships where entity is admin')
    args = parser.parse_args()

    zip_path = args.zip_path
    limit = args.limit
    filter_str = args.filter.lower() if args.filter else None
    filter_admin = args.filter_admin

    if limit != ':' and not limit.isdigit():
        print("[ERROR] The 'limit' must be an integer or ':'.")
        sys.exit(1)

    print("[INFO] Reading data from ZIP...")
    sid_map, relaciones, conteo_por_tipo = parse_json(zip_path)

    kerberoastables = []
    asrep_roastables = []
    admins = []
    obsolete_computers = []
    disabled_admins = []
    pwd_never_expire = []

    for sid, entity in sid_map.items():
        if is_admin(entity):
            admins.append(entity)
        if is_kerberoastable(entity):
            kerberoastables.append(entity)
        if is_asrep_roastable(entity):
            asrep_roastables.append(entity)
        if is_admin(entity) and is_disabled(entity):
            disabled_admins.append(entity)
        if pwd_never_expires(entity):
            pwd_never_expire.append(entity)
        if is_old_os(entity):
            obsolete_computers.append(entity)

    def print_entities(title, entities):
        print(f"- {title}: {len(entities)}")
        if entities:
            shown = get_display_items(entities, limit)
            for u in shown:
                name = u.get("Properties", {}).get("name", "Unknown")
                tipo = u.get("_tipo", "Unknown")
                # Apply filter if set
                if filter_str:
                    if filter_str not in name.lower() and filter_str not in tipo.lower():
                        continue
                print(f"   • {name} ({tipo})")
            if limit != ':' and len(entities) > int(limit):
                print(f"  ... ({len(entities) - int(limit)} more)")
        else:
            print("   (none)")

    print("\n=== DETECTED ENTITIES ===")
    print(f"- Total entities: {len(sid_map)}")
    print("  Breakdown:")
    # Mostrar conteo por tipo con formato, usando las keys en el dict:
    for t in ["users", "computers", "groups", "containers", "ous", "domains", "gpos"]:
        print(f"   • {t.capitalize()}: {conteo_por_tipo.get(t, 0)}")

    print("\n=== POTENTIALLY CRITICAL ASSETS ===")
    print_entities("Kerberoastable accounts", kerberoastables)
    print_entities("AS-REP Roastable accounts", asrep_roastables)
    print_entities("AdminCount=true accounts", admins)
    print(f"- Computers with obsolete OS: {len(obsolete_computers)}")
    if obsolete_computers:
        shown = get_display_items(obsolete_computers, limit)
        for u in shown:
            name = u.get("Properties", {}).get("name", "Unknown")
            os_name = u.get("Properties", {}).get("operatingsystem", "Unknown OS")
            if filter_str and filter_str not in name.lower() and filter_str not in u.get("_tipo", "").lower():
                continue
            print(f"   • {name} - {os_name}")
        if limit != ':' and len(obsolete_computers) > int(limit):
            print(f"  ... ({len(obsolete_computers) - int(limit)} more)")
    else:
        print("   (none)")
    print_entities("Disabled admins", disabled_admins)
    print_entities("Users with passwords that never expire", pwd_never_expire)

    # Apply filtering on relationships:
    filtered_rels = []
    for rel in relaciones:
        # Skip if filter_admin is set and dest is admin
        dest_sid = rel.get("destino_sid", "")
        dest_entity = sid_map.get(dest_sid)
        if filter_admin and dest_entity and is_admin(dest_entity):
            continue

        # Filter by text if filter_str is set:
        if filter_str:
            # Check origin name/type
            origin_name = rel.get("origen_nombre", "").lower()
            origin_type = rel.get("origen_tipo", "").lower()
            derecho = rel.get("derecho", "").lower()

            # Also check destination name/type
            dest_name = dest_entity.get("Properties", {}).get("name", "").lower() if dest_entity else rel.get("destino_sid", "").lower()
            dest_type = dest_entity.get("_tipo", "").lower() if dest_entity else rel.get("destino_tipo", "").lower()

            if (filter_str not in origin_name and filter_str not in origin_type and
                filter_str not in dest_name and filter_str not in dest_type and
                filter_str not in derecho):
                continue

        filtered_rels.append(rel)

    print("\n=== DETECTED RELATIONSHIPS ===")
    print(f"- Total relationships: {len(filtered_rels)}")
    if filtered_rels:
        shown = get_display_items(filtered_rels, limit)
        for rel in shown:
            origin = f"{rel['origen_nombre']} ({rel['origen_tipo']})"
            dest_sid = rel.get("destino_sid", "Unknown")
            dest_entity = sid_map.get(dest_sid, None)
            if dest_entity:
                dest_name = dest_entity.get("Properties", {}).get("name", dest_sid)
                dest_type = dest_entity.get("_tipo", rel.get("destino_tipo", "Unknown"))
            else:
                dest_name = dest_sid
                dest_type = rel.get("destino_tipo", "Unknown")
            dest = f"{dest_name} ({dest_type})"
            print(f"  {dest} --[{rel['derecho']}]--> {origin}")
        if limit != ':' and len(filtered_rels) > int(limit):
            print(f"  ... ({len(filtered_rels) - int(limit)} more relationships)")
    else:
        print("   (none)")

if __name__ == "__main__":
    main()
