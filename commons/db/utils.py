from django.shortcuts import render
from django.utils.text import capfirst
from django.utils.html import format_html, mark_safe, format_html_join


from django.shortcuts import render
from django.utils.text import capfirst


from django.shortcuts import render
from django.utils.text import capfirst


def safe_str(val):
    """Ensure value is JSON serializable."""
    if val is None:
        return ""
    try:
        return str(val)
    except Exception:
        return repr(val)


class AdminChangePreviewMixin:
    """
    Django Admin mixin to show confirmation preview BEFORE saving,
    including inline changes.
    """

    enable_change_preview = True
    exclude_preview_fields = set()
    SAVE_ACTIONS = {"_save", "_addanother", "_continue"}

    # ----------------------------
    # Parent changes
    # ----------------------------
    def _collect_parent_changes(self, form):
        changes = []

        for field in form.changed_data:
            if field in self.exclude_preview_fields:
                continue

            label = form.fields[field].label or capfirst(field)

            changes.append({
                "kind": "parent",
                "field": safe_str(label),
                "old": safe_str(form.initial.get(field)),
                "new": safe_str(form.cleaned_data.get(field)),
            })

        return changes

    # ----------------------------
    # Inline changes
    # ----------------------------
    def _collect_inline_changes(self, request, obj):
        changes = []

        for FormSet, inline in self.get_formsets_with_inlines(request, obj):
            formset = FormSet(request.POST, request.FILES, instance=obj)

            if not formset.is_valid():
                continue

            inline_label = getattr(
                inline,
                "verbose_name_plural",
                inline.model._meta.verbose_name_plural
            )

            inline_label = safe_str(inline_label)

            # Changed / Added
            for form in formset.forms:
                if not hasattr(form, "cleaned_data"):
                    continue

                if not form.cleaned_data:
                    continue

                # Skip empty forms
                if form.cleaned_data.get("DELETE", False):
                    continue

                is_new = form.instance.pk is None

                for field in getattr(form, "changed_data", []):
                    label = form.fields[field].label or capfirst(field)

                    changes.append({
                        "kind": "inline_added" if is_new else "inline",
                        "inline": inline_label,
                        "field": safe_str(label),
                        "old": "" if is_new else safe_str(form.initial.get(field)),
                        "new": safe_str(form.cleaned_data.get(field)),
                    })

            # Deleted
            for deleted_form in getattr(formset, "deleted_forms", []):
                instance = deleted_form.instance
                changes.append({
                    "kind": "inline_deleted",
                    "inline": inline_label,
                    "field": safe_str(instance),
                    "old": safe_str(instance),
                    "new": "Deleted",
                })

        return changes


    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):

        if (
            self.enable_change_preview
            and request.method == "POST"
            and not request.POST.get("_confirm_save")
            and self.SAVE_ACTIONS.intersection(request.POST.keys())
        ):
            obj = self.get_object(request, object_id)
            form = self.get_form(request)(request.POST, instance=obj)

            if form.is_valid():
                changes = []

                # Parent
                changes.extend(self._collect_parent_changes(form))

                # Inline
                changes.extend(self._collect_inline_changes(request, obj))

                if changes:
                    request.session["_admin_confirm_post"] = request.POST.dict()
                    request.session["_admin_confirm_changes"] = changes

                    return render(
                        request,
                        "admin/confirm_changes.html",
                        {
                            "opts": self.model._meta,
                            "object": obj,
                            "changes": changes,
                        },
                    )

        # Restore POST after confirmation
        if request.POST.get("_confirm_save"):
            saved_post = request.session.pop("_admin_confirm_post", None)
            if saved_post:
                request.POST = request.POST.copy()
                request.POST.update(saved_post)

        return super().changeform_view(
            request, object_id, form_url, extra_context
        )
    

def change_preview(instance, request, obj):
    """
    Universal change preview handler for Django Admin
    """

    if "_confirm_save" in request.POST:
        return None  # continue normal flow

    form = instance.get_form(request)(request.POST, instance=obj)

    if not form.is_valid() or not form.changed_data:
        return None

    changes = []
    for field in form.changed_data:
        label = str(form.fields[field].label or capfirst(field))
        changes.append({
            "field": label,
            "old": str(form.initial.get(field)),
            "new": str(form.cleaned_data.get(field)),
        })

    request.session["_admin_pending_post"] = request.POST
    request.session["_admin_changes_preview"] = changes

    return render(
        request,
        "admin/confirm_changes.html",
        {
            "opts": instance.model._meta,
            "object": obj,
            "changes": changes,
        },
    )




def render_scrollable_text(
    value: str,
    tooltip:str,
    *,
    width="380px",
    height="90px",
    empty_label="-",
):
    """
    Render long text in a fixed-size scrollable box with tooltip.
    """

    if not value:
        return empty_label

    return format_html(
        """
        <div
            style="
                width: {width} !important;
                height: {height} !important;
                overflow-y: auto;
                overflow-x: hidden;
                white-space: pre-wrap;
                word-break: break-word;
                padding: 6px 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 12px;
                line-height: 1.4;
            "
            title="{tooltip}"
        >
            {content}
        </div>
        """,
        width=width,
        height=height,
        tooltip=tooltip,   # FULL TEXT on hover
        content="\n".join([v.strip() for v in value.strip().split(",")]),   # visible text (scrollable)
    )