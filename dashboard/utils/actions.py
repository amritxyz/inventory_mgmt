from django.urls import reverse

ACTION_REGISTRY = {
    "transact": {
        "label": "Transact",
        "url_name": None,
        "method": "get",
    },
    "edit": {
        "label": "Edit",
        "url_name": None,
        "method": "get",
    },
    "delete": {
        "label": "Delete",
        "url_name": None,
        "method": "post",
    },
    "approve": {
        "label": "Approve",
        "url_name": None,
        "method": "post",
    },
    "deactivate": {
        "label": "Deactivate",
        "url_name": None,
        "method": "post",
    },
}

MODEL_ACTIONS = {
    "product": {
        "edit": "dashboard:product_update",
        "delete": "dashboard:product_delete",
    },
    "variant": {
        "transact": "dashboard:transaction_create",
        "edit": "dashboard:variant_update",
        "delete": "dashboard:variant_delete",
    },
    "transaction": {
        "edit": "dashboard:transaction_update",
        "delete": "dashboard:transaction_delete",
    },
    "user": {
        "approve": "dashboard:user_approve",
        "deactivate": "dashboard:user_toggle",
        "delete": "dashboard:user_delete",
    },
}

def resolve_actions(model_key, actions, obj, request=None):
    resolved = []
    user = request.user if request else None

    for action_key in actions:
        if model_key == "user":
            if action_key == "approve" and getattr(obj, "is_active", False):
                continue
            if action_key == "deactivate" and (not getattr(obj, "is_active", False) or obj == user):
                continue
            if action_key == "delete" and obj == user:
                continue

        meta = ACTION_REGISTRY[action_key]
        url_name = MODEL_ACTIONS[model_key][action_key]

        if action_key == "transact":
            url = reverse(url_name) + f"?variant={obj.pk}"
        else:
            url = reverse(url_name, args=[obj.pk])

        resolved.append({
            "label": meta["label"],
            "url": url,
            "method": meta["method"],
        })

    return resolved
