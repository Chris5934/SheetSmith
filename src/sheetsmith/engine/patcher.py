"""Patch management and application engine."""

import uuid
from datetime import datetime
from typing import Optional

from ..sheets import GoogleSheetsClient, BatchUpdate
from ..sheets.models import Patch
from ..memory import MemoryStore, AuditLog
from .differ import FormulaDiffer, PatchPreview


class PatchEngine:
    """Engine for creating, managing, and applying formula patches."""

    def __init__(
        self,
        sheets_client: Optional[GoogleSheetsClient] = None,
        memory_store: Optional[MemoryStore] = None,
    ):
        self.sheets_client = sheets_client or GoogleSheetsClient()
        self.memory_store = memory_store
        self.differ = FormulaDiffer()
        self._pending_patches: dict[str, Patch] = {}

    def create_patch(
        self,
        spreadsheet_id: str,
        description: str,
        changes: list[dict],
    ) -> Patch:
        """Create a new patch from a list of changes."""
        patch = Patch(
            id=str(uuid.uuid4()),
            spreadsheet_id=spreadsheet_id,
            description=description,
            changes=changes,
            created_at=datetime.utcnow().isoformat(),
            status="pending",
        )
        self._pending_patches[patch.id] = patch
        return patch

    def create_patch_from_preview(self, preview: PatchPreview) -> Patch:
        """Create a patch from a PatchPreview."""
        changes = [
            {
                "sheet": diff.sheet,
                "cell": diff.cell,
                "old": diff.old_formula,
                "new": diff.new_formula,
            }
            for diff in preview.diffs
        ]
        return self.create_patch(
            spreadsheet_id=preview.spreadsheet_id,
            description=preview.description,
            changes=changes,
        )

    def get_patch(self, patch_id: str) -> Optional[Patch]:
        """Get a pending patch by ID."""
        return self._pending_patches.get(patch_id)

    def list_pending_patches(self) -> list[Patch]:
        """List all pending patches."""
        return [p for p in self._pending_patches.values() if p.status == "pending"]

    async def apply_patch(self, patch_id: str, user_approved: bool = True) -> dict:
        """Apply a pending patch to the spreadsheet."""
        patch = self._pending_patches.get(patch_id)
        if not patch:
            return {"success": False, "error": "Patch not found"}

        if patch.status != "pending":
            return {"success": False, "error": f"Patch is already {patch.status}"}

        if not user_approved:
            patch.status = "rejected"
            return {"success": False, "error": "Patch was not approved"}

        # Build batch update
        batch = BatchUpdate(
            spreadsheet_id=patch.spreadsheet_id,
            description=patch.description,
        )

        for change in patch.changes:
            batch.add_update(
                sheet_name=change["sheet"],
                cell=change["cell"],
                new_formula=change["new"],
            )

        # Apply the update
        result = self.sheets_client.batch_update(batch)

        if result.success:
            patch.status = "applied"

            # Log the action if memory store is available
            if self.memory_store:
                await self.memory_store.log_action(
                    AuditLog(
                        id=str(uuid.uuid4()),
                        action="batch_update",
                        spreadsheet_id=patch.spreadsheet_id,
                        description=patch.description,
                        details={
                            "patch_id": patch.id,
                            "changes": len(patch.changes),
                        },
                        user_approved=user_approved,
                        changes_applied=result.updated_cells,
                    )
                )

            return {
                "success": True,
                "patch_id": patch.id,
                "updated_cells": result.updated_cells,
                "message": f"Successfully applied {result.updated_cells} changes",
            }
        else:
            patch.status = "failed"
            return {
                "success": False,
                "error": result.errors[0] if result.errors else "Unknown error",
                "all_errors": result.errors,
            }

    def reject_patch(self, patch_id: str, reason: str = "") -> dict:
        """Reject a pending patch."""
        patch = self._pending_patches.get(patch_id)
        if not patch:
            return {"success": False, "error": "Patch not found"}

        patch.status = "rejected"
        message = "Patch rejected"
        if reason:
            message += f": {reason}"
        return {
            "success": True,
            "patch_id": patch.id,
            "message": message,
        }

    def generate_value_replacement_patch(
        self,
        spreadsheet_id: str,
        matches: list[dict],
        old_value: str,
        new_value: str,
        description: str,
    ) -> Patch:
        """Generate a patch for replacing a value across matched formulas."""
        preview = self.differ.generate_replacement_patch(
            spreadsheet_id=spreadsheet_id,
            matches=matches,
            old_value=old_value,
            new_value=new_value,
            description=description,
        )
        return self.create_patch_from_preview(preview)

    def preview_patch(self, patch_id: str) -> Optional[str]:
        """Get a human-readable preview of a patch."""
        patch = self.get_patch(patch_id)
        if not patch:
            return None
        return patch.to_diff_string()
