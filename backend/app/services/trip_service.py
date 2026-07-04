from __future__ import annotations

from dataclasses import asdict

from app.services.auth_service import auth_service
from app.services.in_app_notification_service import in_app_notification_service
from app.services.notification_templates import (
    trip_created_template,
    trip_invite_response_template,
    trip_invite_sent_template,
)
from app.services.realtime_service import realtime_service
from app.services.trip_store import InviteStatus, MemberRole, build_trip_store, normalize_member_identifier


class TripService:
    def __init__(self) -> None:
        self._store = build_trip_store()

    def _send_trip_invite_email(self, *, recipient_email: str, trip_name: str, inviter_name: str, member_name: str | None = None) -> dict:
        display_name = member_name or recipient_email
        email_html = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2 style="color: #2c3e50;">You have been added to '{trip_name}'</h2>
            <p>Hi {display_name},</p>
            <p>{inviter_name} added you to '{trip_name}' on TripWise.</p>
            <p>Please open the app and accept the trip invite to start tracking expenses together.</p>
            <p style="margin-top: 2rem; color: #7f8c8d; font-size: 0.9rem;">
                TripWise - Simplify group expenses
            </p>
        </div>
        """
        from app.services.notification_service import notification_service

        return notification_service.enqueue_email(
            recipient=recipient_email,
            subject=f"You have been added to '{trip_name}' on TripWise",
            html_content=email_html,
            metadata={"tripName": trip_name, "eventType": "trip_invited", "recipientEmail": recipient_email},
        )

    def create_trip(
        self,
        *,
        trip_name: str,
        creator_identifier: str,
        creator_name: str | None,
        member_identifiers: list[str],
        creation_mode: str = "dynamic",
        member_entries: list[dict] | None = None,
    ) -> dict:
        normalized_creator = normalize_member_identifier(creator_identifier)
        creator = self._store.ensure_profile_for_identifier(
            identifier=normalized_creator,
            display_name=creator_name,
        )
        entries = member_entries or []
        normalized_invitees = self._normalize_unique_identifiers(member_identifiers)
        trip = self._store.create_trip(
            name=trip_name,
            creator_profile_id=creator.profile_id,
            member_count=1,
        )

        creator_member = self._store.add_trip_member(
            trip_id=trip.trip_id,
            profile_id=creator.profile_id,
            guest_identifier=None,
            role="admin",
            invite_status="accepted",
        )

        invite_results: list[dict] = []
        if creation_mode == "self":
            member_names = [str(entry.get("name") or "").strip() for entry in entries]
            member_names = [name for name in member_names if name]
            for index, member_name in enumerate(member_names):
                member = self._store.add_trip_member(
                    trip_id=trip.trip_id,
                    profile_id=None,
                    guest_identifier=member_name,
                    role="member",
                    invite_status="accepted",
                )
                invite_results.append(
                    {
                        "memberId": member.member_id,
                        "name": member_name,
                        "identifier": member_name,
                        "mode": "name_only_no_invite",
                        "inviteStatus": member.invite_status,
                        "memberNumber": index + 1,
                        "hasAccount": False,
                        "inviteSent": False,
                    }
                )
        else:
            dynamic_entries = entries if entries else [{"email": identifier, "name": ""} for identifier in normalized_invitees]
            for entry in dynamic_entries:
                identifier = str(entry.get("email") or "").strip()
                if not identifier:
                    continue
                normalized = normalize_member_identifier(identifier)
                is_registered = auth_service.is_registered_identifier(identifier=normalized)

                if is_registered:
                    profile = self._store.ensure_profile_for_identifier(
                        identifier=normalized,
                        display_name=str(entry.get("name") or "").strip() or None,
                    )
                    member = self._store.add_trip_member(
                        trip_id=trip.trip_id,
                        profile_id=profile.profile_id,
                        guest_identifier=None,
                        role="member",
                        invite_status="pending",
                    )
                    invite_results.append(
                        {
                            "memberId": member.member_id,
                            "name": str(entry.get("name") or "").strip() or None,
                            "identifier": normalized,
                            "mode": "registered_invite",
                            "inviteStatus": member.invite_status,
                            "hasAccount": True,
                            "inviteSent": True,
                        }
                    )
                    if profile.email:
                        invite_results[-1]["emailNotification"] = self._send_trip_invite_email(
                            recipient_email=profile.email,
                            trip_name=trip.name,
                            inviter_name=creator.name or creator.email,
                            member_name=profile.name or profile.email,
                        )
                else:
                    member = self._store.add_trip_member(
                        trip_id=trip.trip_id,
                        profile_id=None,
                        guest_identifier=normalized,
                        role="member",
                        invite_status="pending",
                    )
                    invite_results.append(
                        {
                            "memberId": member.member_id,
                            "name": str(entry.get("name") or "").strip() or None,
                            "identifier": normalized,
                            "mode": "guest_view_only",
                            "inviteStatus": member.invite_status,
                            "hasAccount": False,
                            "inviteSent": False,
                        }
                    )
                    if "@" in normalized:
                        invite_results[-1]["emailNotification"] = self._send_trip_invite_email(
                            recipient_email=normalized,
                            trip_name=trip.name,
                            inviter_name=creator.name or creator.email,
                            member_name=str(entry.get("name") or "").strip() or None,
                        )

        member_count = self._sync_trip_member_count(trip_id=trip.trip_id)

        created_title, created_message = trip_created_template(
            trip_name=trip.name,
            creator_name=creator.name,
        )
        created_notifications = in_app_notification_service.notify_trip_members(
            trip_id=trip.trip_id,
            event_type="trip_created",
            title=created_title,
            message=created_message,
            metadata={
                "tripId": trip.trip_id,
                "tripName": trip.name,
                "creatorProfileId": creator.profile_id,
            },
            exclude_member_ids={creator_member.member_id},
            send_whatsapp=True,
            allowed_invite_statuses={"accepted", "pending"},
        )

        return {
            "trip": asdict(trip),
            "invites": invite_results,
            "summary": {
                "registeredInviteCount": len([i for i in invite_results if i["mode"] == "registered_invite"]),
                "guestCount": len([i for i in invite_results if i["mode"] == "guest_view_only"]),
                "localMemberCount": len([i for i in invite_results if i["mode"] == "name_only_no_invite"]),
                "memberCount": member_count,
            },
            "notifications": created_notifications,
        }

    def list_trips(self, *, creator_identifier: str) -> dict:
        normalized_identifier = normalize_member_identifier(creator_identifier)
        profile = self._store.find_profile_by_identifier(normalized_identifier)
        profile_id = profile.profile_id if profile else None
        trips = self._store.list_trips_for_identifier(
            identifier=normalized_identifier,
            profile_id=profile_id,
        )
        result: list[dict] = []
        for trip in trips:
            synced_count = self._sync_trip_member_count(trip_id=trip.trip_id)
            data = asdict(trip)
            data["member_count"] = synced_count
            role, invite_status, member_id = self._resolve_my_membership(
                trip_id=trip.trip_id,
                normalized_identifier=normalized_identifier,
                profile_id=profile_id,
            )
            data["my_role"] = role
            data["my_invite_status"] = invite_status
            data["my_member_id"] = member_id
            result.append(data)
        return {"trips": result}

    def _resolve_role_for_trip(self, *, trip_id: str, normalized_identifier: str, profile_id: str | None) -> str:
        role, _, _ = self._resolve_my_membership(
            trip_id=trip_id,
            normalized_identifier=normalized_identifier,
            profile_id=profile_id,
        )
        return role

    def _resolve_my_membership(self, *, trip_id: str, normalized_identifier: str, profile_id: str | None) -> tuple[str, str, str | None]:
        trip = self._store.get_trip(trip_id=trip_id)
        if trip is None:
            return ("unknown", "unknown", None)

        role = "unknown"
        invite_status = "unknown"
        member_id = None

        if profile_id and trip.created_by == profile_id:
            role = "creator"
            invite_status = "accepted"

        members = self._store.list_trip_members(trip_id=trip_id)
        for member in members:
            is_match = False
            if profile_id and member.profile_id == profile_id:
                is_match = True
            elif member.guest_identifier and normalize_member_identifier(member.guest_identifier) == normalized_identifier:
                is_match = True

            if is_match:
                if role == "unknown":
                    role = member.role
                invite_status = member.invite_status
                member_id = member.member_id
                break

        return (role, invite_status, member_id)

    def list_members(self, *, trip_id: str) -> dict:
        members = self._store.list_trip_members(trip_id=trip_id)
        return {
            "members": [
                {
                    "memberId": m.member_id,
                    "tripId": m.trip_id,
                    "profileId": m.profile_id,
                    "identifier": self._member_identifier(member_id=m.member_id),
                    "role": m.role,
                    "inviteStatus": m.invite_status,
                    "canEdit": m.role in {"admin", "member"} and m.invite_status == "accepted",
                }
                for m in members
            ]
        }

    def list_split_eligible_members(self, *, trip_id: str) -> dict:
        members = self._store.list_trip_members(trip_id=trip_id)
        eligible = [m for m in members if m.invite_status == "accepted"]
        return {
            "eligibleMembers": [
                {
                    "memberId": m.member_id,
                    "profileId": m.profile_id,
                    "identifier": m.guest_identifier,
                    "role": m.role,
                    "inviteStatus": m.invite_status,
                }
                for m in eligible
            ]
        }

    def invite_member(self, *, trip_id: str, identifier: str, actor_identifier: str | None = None) -> dict:
        normalized = normalize_member_identifier(identifier)
        if not self.is_trip_editable(trip_id=trip_id):
            raise ValueError("trip is closed and no edits are allowed")
        if actor_identifier:
            actor = self.resolve_member_for_identifier(trip_id=trip_id, identifier=actor_identifier)
            if actor is None or actor["inviteStatus"] != "accepted":
                raise ValueError("actor is not an accepted trip member")
            if actor["role"] != "admin":
                raise ValueError("only admin can invite members")
        self._ensure_identifier_not_already_member(trip_id=trip_id, identifier=normalized)

        trip = self._store.get_trip(trip_id=trip_id)
        trip_name = trip.name if trip else "your trip"
        if auth_service.is_registered_identifier(identifier=normalized):
            profile = self._store.ensure_profile_for_identifier(
                identifier=normalized,
                display_name=None,
            )
            member = self._store.add_trip_member(
                trip_id=trip_id,
                profile_id=profile.profile_id,
                guest_identifier=None,
                role="member",
                invite_status="pending",
            )
            member_count = self._sync_trip_member_count(trip_id=trip_id)
            invite_title, invite_message = trip_invite_sent_template(
                trip_name=trip_name,
                inviter_name="Trip admin",
            )
            notification_result = in_app_notification_service.notify_trip_member(
                trip_id=trip_id,
                member_id=member.member_id,
                event_type="trip_invited",
                title=invite_title,
                message=invite_message,
                metadata={"tripId": trip_id, "tripName": trip_name},
                send_whatsapp=False,
            )
            if profile.email:
                self._send_trip_invite_email(
                    recipient_email=profile.email,
                    trip_name=trip_name,
                    inviter_name="Trip admin",
                    member_name=profile.name or profile.email,
                )
            
            return {
                "memberId": member.member_id,
                "identifier": normalized,
                "mode": "registered_invite",
                "inviteStatus": member.invite_status,
                "notification": notification_result,
                "memberCount": member_count,
            }

        member = self._store.add_trip_member(
            trip_id=trip_id,
            profile_id=None,
            guest_identifier=normalized,
            role="guest",
            invite_status="pending",
        )
        member_count = self._sync_trip_member_count(trip_id=trip_id)
        return {
            "memberId": member.member_id,
            "identifier": normalized,
            "mode": "guest_view_only",
            "inviteStatus": member.invite_status,
            "memberCount": member_count,
        }

    def invite_all_members(self, *, trip_id: str, identifiers: list[str], actor_identifier: str | None = None) -> dict:
        if not self.is_trip_editable(trip_id=trip_id):
            raise ValueError("trip is closed and no edits are allowed")

        if actor_identifier:
            actor = self.resolve_member_for_identifier(trip_id=trip_id, identifier=actor_identifier)
            if actor is None or actor["inviteStatus"] != "accepted":
                raise ValueError("actor is not an accepted trip member")
            if actor["role"] != "admin":
                raise ValueError("only admin can send invite-all")

        normalized = self._normalize_unique_identifiers(identifiers)
        results: list[dict] = []
        skipped: list[dict] = []

        for identifier in normalized:
            try:
                if actor_identifier:
                    result = self.invite_member(
                        trip_id=trip_id,
                        identifier=identifier,
                        actor_identifier=actor_identifier,
                    )
                else:
                    result = self.invite_member(trip_id=trip_id, identifier=identifier)
                results.append(result)
            except ValueError as exc:
                skipped.append({"identifier": identifier, "reason": str(exc)})

        member_count = self._sync_trip_member_count(trip_id=trip_id)
        return {
            "tripId": trip_id,
            "invited": results,
            "skipped": skipped,
            "summary": {
                "requested": len(normalized),
                "invitedCount": len(results),
                "skippedCount": len(skipped),
                "memberCount": member_count,
            },
        }

    def respond_invite(self, *, member_id: str, action: InviteStatus, actor_identifier: str | None = None) -> dict:
        if action not in {"accepted", "rejected"}:
            raise ValueError("action must be accepted or rejected")
        existing = self._store.get_trip_member(member_id=member_id)
        if existing is None:
            raise ValueError("member not found")
        if actor_identifier:
            actor = self.resolve_member_for_identifier(trip_id=existing.trip_id, identifier=actor_identifier)
            if actor is None:
                raise ValueError("actor is not a trip member")
            if actor["memberId"] != member_id:
                raise ValueError("only the invitee can accept or reject their own invitation")
        if existing.invite_status == action:
            return {
                "memberId": existing.member_id,
                "tripId": existing.trip_id,
                "inviteStatus": existing.invite_status,
                "notifications": {"skipped": True, "reason": "already_in_state"},
            }

        updated = self._store.update_trip_member_status(member_id=member_id, status=action)
        self._sync_trip_member_count(trip_id=updated.trip_id)
        trip = self._store.get_trip(trip_id=updated.trip_id)
        trip_name = trip.name if trip else "trip"
        responder_name = self._member_display_name(member_id=updated.member_id)
        response_title, response_message = trip_invite_response_template(
            trip_name=trip_name,
            member_name=responder_name,
            accepted=action == "accepted",
        )
        event_type = "trip_invite_accepted" if action == "accepted" else "trip_invite_rejected"
        notification_result = in_app_notification_service.notify_trip_members(
            trip_id=updated.trip_id,
            event_type=event_type,
            title=response_title,
            message=response_message,
            metadata={"tripId": updated.trip_id, "memberId": updated.member_id, "inviteStatus": action},
            exclude_member_ids={updated.member_id},
            send_whatsapp=True,
        )
        return {
            "memberId": updated.member_id,
            "tripId": updated.trip_id,
            "inviteStatus": updated.invite_status,
            "notifications": notification_result,
        }

    def reinvite_member(self, *, member_id: str, actor_identifier: str | None = None) -> dict:
        existing = self._store.get_trip_member(member_id=member_id)
        if existing is None:
            raise ValueError("member not found")
        if actor_identifier:
            actor = self.resolve_member_for_identifier(trip_id=existing.trip_id, identifier=actor_identifier)
            if actor is None or actor["inviteStatus"] != "accepted":
                raise ValueError("actor is not an accepted trip member")
            if actor["role"] != "admin":
                raise ValueError("only admin can re-invite members")
        if existing.invite_status == "accepted":
            raise ValueError("accepted members cannot be re-invited")

        updated = self._store.reinvite_member(member_id=member_id)
        self._sync_trip_member_count(trip_id=updated.trip_id)
        
        # Send reinvite email
        if updated.profile_id:
            profile = self._store.get_profile_by_id(profile_id=updated.profile_id)
            trip = self._store.get_trip(trip_id=updated.trip_id)
            if profile and profile.email and trip:
                email_html = f"""
                <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <h2 style="color: #2c3e50;">Reminder: You're invited to '{trip.name}'!</h2>
                    <p>This is a reminder that Trip admin has invited you to join '{trip.name}' on TripWise.</p>
                    <p>Accept the invite in the app to start tracking expenses together.</p>
                    <p style="margin-top: 2rem; color: #7f8c8d; font-size: 0.9rem;">
                        TripWise - Simplify group expenses
                    </p>
                </div>
                """
                from app.services.notification_service import notification_service
                notification_service.enqueue_email(
                    recipient=profile.email,
                    subject=f"Reminder: Join '{trip.name}' on TripWise",
                    html_content=email_html,
                    metadata={"tripId": updated.trip_id, "eventType": "trip_reinvited", "memberId": updated.member_id},
                )
        
        return {
            "memberId": updated.member_id,
            "tripId": updated.trip_id,
            "inviteStatus": updated.invite_status,
        }

    def remove_member(self, *, member_id: str, actor_identifier: str | None = None) -> dict:
        existing = self._store.get_trip_member(member_id=member_id)
        if existing is None:
            raise ValueError("member not found")
        if actor_identifier:
            actor = self.resolve_member_for_identifier(trip_id=existing.trip_id, identifier=actor_identifier)
            if actor is None or actor["inviteStatus"] != "accepted":
                raise ValueError("actor is not an accepted trip member")
            if actor["role"] != "admin":
                raise ValueError("only admin can remove members")

        trip_members = self._store.list_trip_members(trip_id=existing.trip_id)
        accepted_admins = [m for m in trip_members if m.role == "admin" and m.invite_status == "accepted"]
        if existing.role == "admin" and existing.invite_status == "accepted" and len(accepted_admins) <= 1:
            raise ValueError("cannot remove the last accepted admin")

        self._store.remove_trip_member(member_id=member_id)
        member_count = self._sync_trip_member_count(trip_id=existing.trip_id)
        return {"removed": True, "memberId": member_id, "memberCount": member_count}

    def update_member_role(self, *, member_id: str, actor_identifier: str, role: MemberRole) -> dict:
        if role not in {"admin", "member", "guest"}:
            raise ValueError("invalid role")

        target_member = self._store.get_trip_member(member_id=member_id)
        if target_member is None:
            raise ValueError("member not found")
        if not self.is_trip_editable(trip_id=target_member.trip_id):
            raise ValueError("trip is closed and no edits are allowed")

        actor = self.resolve_member_for_identifier(trip_id=target_member.trip_id, identifier=actor_identifier)
        if actor is None or actor["inviteStatus"] != "accepted":
            raise ValueError("actor is not an accepted trip member")
        if actor["role"] != "admin":
            raise ValueError("only admin can update member role")

        updated = self._store.update_trip_member_role(member_id=member_id, role=role)
        event = realtime_service.publish_trip_event(
            event_type="member_role_updated",
            trip_id=updated.trip_id,
            payload={"memberId": updated.member_id, "role": updated.role},
        )
        return {
            "member": {
                "memberId": updated.member_id,
                "tripId": updated.trip_id,
                "profileId": updated.profile_id,
                "identifier": updated.guest_identifier,
                "role": updated.role,
                "inviteStatus": updated.invite_status,
                "canEdit": updated.role in {"admin", "member"} and updated.invite_status == "accepted",
            },
            "event": event,
        }

    def resolve_member_for_identifier(self, *, trip_id: str, identifier: str) -> dict | None:
        normalized = normalize_member_identifier(identifier)
        profile = self._store.find_profile_by_identifier(normalized)
        members = self._store.list_trip_members(trip_id=trip_id)

        if profile:
            for member in members:
                if member.profile_id == profile.profile_id:
                    return {
                        "memberId": member.member_id,
                        "tripId": member.trip_id,
                        "profileId": member.profile_id,
                        "role": member.role,
                        "inviteStatus": member.invite_status,
                    }

        for member in members:
            if member.guest_identifier == normalized:
                return {
                    "memberId": member.member_id,
                    "tripId": member.trip_id,
                    "profileId": member.profile_id,
                    "role": member.role,
                    "inviteStatus": member.invite_status,
                }

        return None

    def split_eligible_member_ids(self, *, trip_id: str) -> set[str]:
        members = self._store.list_trip_members(trip_id=trip_id)
        return {m.member_id for m in members if m.invite_status == "accepted"}

    def get_member(self, *, member_id: str) -> dict | None:
        member = self._store.get_trip_member(member_id=member_id)
        if member is None:
            return None
        return {
            "memberId": member.member_id,
            "tripId": member.trip_id,
            "profileId": member.profile_id,
            "identifier": member.guest_identifier,
            "role": member.role,
            "inviteStatus": member.invite_status,
            "canEdit": member.role in {"admin", "member"} and member.invite_status == "accepted",
        }

    def get_trip(self, *, trip_id: str) -> dict | None:
        trip = self._store.get_trip(trip_id=trip_id)
        if not trip:
            return None
        data = asdict(trip)
        data["member_count"] = self._sync_trip_member_count(trip_id=trip_id)
        return data

    def rename_trip(self, *, trip_id: str, actor_identifier: str, name: str) -> dict:
        next_name = name.strip()
        if len(next_name) < 2:
            raise ValueError("trip name must be at least 2 characters")

        actor = self.resolve_member_for_identifier(trip_id=trip_id, identifier=actor_identifier)
        if actor is None or actor["inviteStatus"] != "accepted":
            raise ValueError("actor is not an accepted trip member")
        if actor["role"] != "admin":
            raise ValueError("only admin can rename trip")
        if not self.is_trip_editable(trip_id=trip_id):
            raise ValueError("trip is closed and no edits are allowed")

        updated_trip = self._store.set_trip_name(trip_id=trip_id, name=next_name)
        event = realtime_service.publish_trip_event(
            event_type="trip_renamed",
            trip_id=trip_id,
            payload={"tripId": trip_id, "name": updated_trip.name},
        )
        return {"trip": asdict(updated_trip), "event": event}

    def is_trip_editable(self, *, trip_id: str) -> bool:
        trip = self._store.get_trip(trip_id=trip_id)
        if trip is None:
            return False
        return trip.status not in {"closed", "past"}

    def close_trip(self, *, trip_id: str, actor_identifier: str) -> dict:
        actor = self.resolve_member_for_identifier(trip_id=trip_id, identifier=actor_identifier)
        if actor is None or actor["inviteStatus"] != "accepted":
            raise ValueError("actor is not an accepted trip member")
        if actor["role"] != "admin":
            raise ValueError("only admin can close trip")

        trip = self._store.get_trip(trip_id=trip_id)
        if trip is None:
            raise ValueError("trip not found")
        if trip.status in {"closed", "past"}:
            return {"trip": asdict(trip), "alreadyClosed": True}

        closed_trip = self._store.set_trip_status(trip_id=trip_id, status="closed")
        event = realtime_service.publish_trip_event(
            event_type="trip_closed",
            trip_id=trip_id,
            payload={"tripId": trip_id, "status": closed_trip.status},
        )
        return {"trip": asdict(closed_trip), "alreadyClosed": False, "event": event}

    def move_trip_to_past(self, *, trip_id: str, actor_identifier: str) -> dict:
        actor = self.resolve_member_for_identifier(trip_id=trip_id, identifier=actor_identifier)
        if actor is None or actor["inviteStatus"] != "accepted":
            raise ValueError("actor is not an accepted trip member")
        if actor["role"] != "admin":
            raise ValueError("only admin can archive trip")

        trip = self._store.get_trip(trip_id=trip_id)
        if trip is None:
            raise ValueError("trip not found")
        if trip.status == "past":
            return {"trip": asdict(trip), "alreadyPast": True}

        past_trip = self._store.set_trip_status(trip_id=trip_id, status="past")
        event = realtime_service.publish_trip_event(
            event_type="trip_archived",
            trip_id=trip_id,
            payload={"tripId": trip_id, "status": past_trip.status},
        )
        return {"trip": asdict(past_trip), "alreadyPast": False, "event": event}

    def _member_display_name(self, *, member_id: str) -> str:
        member = self._store.get_trip_member(member_id=member_id)
        if member is None:
            return "A member"
        if member.profile_id:
            profile = self._store.get_profile_by_id(profile_id=member.profile_id)
            if profile:
                if profile.name and profile.name.strip():
                    return profile.name.strip()
                if profile.email:
                    return profile.email
                if profile.phone:
                    return profile.phone
        if member.guest_identifier:
            return member.guest_identifier
        return "A member"

    def _member_identifier(self, *, member_id: str) -> str | None:
        member = self._store.get_trip_member(member_id=member_id)
        if member is None:
            return None
        if member.guest_identifier:
            return member.guest_identifier
        if member.profile_id:
            profile = self._store.get_profile_by_id(profile_id=member.profile_id)
            if profile:
                return profile.email or profile.phone
        return None

    def _normalize_unique_identifiers(self, identifiers: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for raw in identifiers:
            normalized = normalize_member_identifier(raw)
            if not normalized:
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped

    def _ensure_identifier_not_already_member(self, *, trip_id: str, identifier: str) -> None:
        members = self._store.list_trip_members(trip_id=trip_id)
        profile = self._store.find_profile_by_identifier(identifier)
        for member in members:
            if member.guest_identifier and member.guest_identifier == identifier:
                raise ValueError("identifier is already invited in this trip")
            if profile and member.profile_id == profile.profile_id:
                raise ValueError("identifier is already invited in this trip")

    def _sync_trip_member_count(self, *, trip_id: str) -> int:
        members = self._store.list_trip_members(trip_id=trip_id)
        member_count = len(members)
        self._store.set_trip_member_count(trip_id=trip_id, member_count=member_count)
        return member_count


trip_service = TripService()
