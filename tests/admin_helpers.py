from commons.utils import sanitize_text
from tests.models import CaseMappings, Collection

def has_value(v):
    return v is not None and str(v).strip() != ""


def normalize_row_collections(row: dict) -> dict:
    clean = {
        key.strip().lower().replace(" ", "_"): sanitize_text(value)
        for key, value in row.items()
    }

    return {
        "collection_name": clean.get("collection_name", "").strip(),
        "tab_name": clean.get("tab_name", "").strip(),
        "embed_link": clean.get("embed_link", "").strip(),
        "transform_iq": clean.get("transform_iq"),
        "sticker": clean.get("sticker"),
        "action_name": clean.get("action_name"),
        "iframe_link": clean.get("collection_iframe_link"),
        "iframe_title": clean.get("collection_iframe_title"),
        "iframe_subtitle": clean.get("collection_iframe_subtitle"),
    }

def build_collection_meta(rows):
    meta_map = {}

    for r in rows:
        name = r["collection_name"]

        if name not in meta_map:
            meta_map[name] = {
                "iframe_link": None,
                "iframe_title": None,
                "iframe_subtitle": None,
            }

        for field, key in [
            ("iframe_link", "iframe_link"),
            ("iframe_title", "iframe_title"),
            ("iframe_subtitle", "iframe_subtitle"),
        ]:
            val = r.get(key)
            if has_value(val):
                # latest value from CSV overrides
                meta_map[name][field] = val

    return meta_map


def upsert_collections(rows):
    meta_map = build_collection_meta(rows)
    names = meta_map.keys()

    existing = {
        c.collection_name: c
        for c in Collection.objects.filter(collection_name__in=names)
    }

    to_create = []
    to_update = []

    for name, meta in meta_map.items():

        if name not in existing:
            to_create.append(
                Collection(
                    collection_name=name,
                    **meta
                )
            )
        else:
            obj = existing[name]
            updated = False

            for field, val in meta.items():
                if has_value(val) and getattr(obj, field) != val:
                    setattr(obj, field, val)
                    updated = True

            if updated:
                to_update.append(obj)

    if to_create:
        Collection.objects.bulk_create(to_create)

    # refresh after create
    existing = {
        c.collection_name: c
        for c in Collection.objects.filter(collection_name__in=names)
    }

    if to_update:
        Collection.objects.bulk_update(
            to_update,
            ["iframe_link", "iframe_title", "iframe_subtitle"],
        )

    return existing, len(to_create)

def upsert_cases(rows, collections_map):
    keys = {(r["collection_name"], r["tab_name"]) for r in rows}

    existing = {
        (c.collection.collection_name, c.tab_name): c
        for c in CaseMappings.objects.select_related("collection")
        .filter(collection__collection_name__in=[k[0] for k in keys])
    }

    to_create = []
    to_update = []

    for r in rows:
        key = (r["collection_name"], r["tab_name"])
        collection = collections_map[r["collection_name"]]

        data = {
            "embed_link": r["embed_link"],
            "transform_iq": r["transform_iq"],
            "sticker": r["sticker"],
            "action_name": r["action_name"],
        }

        if key not in existing:
            create_data = {k: v for k, v in data.items() if has_value(v)}

            to_create.append(
                CaseMappings(
                    collection=collection,
                    tab_name=r["tab_name"],
                    **create_data
                )
            )
        else:
            obj = existing[key]
            updated = False

            for field, val in data.items():
                # ✅ critical rule here
                if has_value(val) and getattr(obj, field) != val:
                    setattr(obj, field, val)
                    updated = True

            if updated:
                to_update.append(obj)

    if to_create:
        CaseMappings.objects.bulk_create(to_create)

    if to_update:
        CaseMappings.objects.bulk_update(
            to_update,
            ["embed_link", "transform_iq", "sticker", "action_name"],
        )

    return len(to_create), len(to_update)


class CSVValidationError(Exception):
    pass


def validate_row(row, row_num):
    errors = []

    if not has_value(row["collection_name"]):
        errors.append("collection_name is required")

    if not has_value(row["tab_name"]):
        errors.append("tab_name is required")

    if errors:
        return errors

    return []
        


def validate_business_rules(rows):
    errors = []

    existing_cases = {
        (c.collection.collection_name, c.tab_name)
        for c in CaseMappings.objects.select_related("collection")
    }

    final_rows = []

    for i, r in enumerate(rows, start=1):
        key = (r["collection_name"], r["tab_name"])

        is_existing_case = key in existing_cases

        # 🔴 New case validation
        if not is_existing_case:
            if not has_value(r["embed_link"]):
                errors.append(f"Row {i}: New case must have embed_link")
                continue


        # 🔴 Existing case validation
        if is_existing_case:
            if not any(
                has_value(r.get(k))
                for k in ["embed_link", "transform_iq", "sticker", "action_name"]
            ):
                errors.append(f"Row {i}: Existing case has nothing to update")
                continue

        final_rows.append(r)

    return final_rows, errors

