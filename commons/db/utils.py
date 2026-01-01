from django.shortcuts import render
from django.utils.text import capfirst
from django.utils.html import format_html, mark_safe, format_html_join


class AdminChangePreviewMixin:
    """
    Django Admin mixin to show a modal-style confirmation popup
    BEFORE saving an object.

    Works for:
    - Save
    - Save and continue editing
    - Save and add another
    """

    enable_change_preview = True
    exclude_preview_fields = set()

    SAVE_ACTIONS = {"_save", "_addanother", "_continue"}

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):

        # 1️⃣ Intercept ALL save buttons (before DB save)
        if (
            self.enable_change_preview
            and request.method == "POST"
            and not request.POST.get("_confirm_save")
            and self.SAVE_ACTIONS.intersection(request.POST.keys())
        ):
            obj = self.get_object(request, object_id)
            form = self.get_form(request)(request.POST, instance=obj)

            if form.is_valid() and form.changed_data:
                changes = []

                for field in form.changed_data:
                    if field in self.exclude_preview_fields:
                        continue

                    label = form.fields[field].label or capfirst(field)
                    changes.append({
                        "field": label,
                        "old": form.initial.get(field),
                        "new": form.cleaned_data.get(field),
                    })

                if changes:
                    # Store POST so we can restore exact action later
                    request.session["_admin_confirm_post"] = request.POST
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

        # 2️⃣ Confirmed → restore POST (including which save button was used)
        if request.POST.get("_confirm_save"):
            request.POST = request.session.pop("_admin_confirm_post", request.POST)

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
        label = form.fields[field].label or capfirst(field)
        changes.append({
            "field": label,
            "old": form.initial.get(field),
            "new": form.cleaned_data.get(field),
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
