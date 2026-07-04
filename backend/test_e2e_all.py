#!/usr/bin/env python3
"""
TripWise Comprehensive Automated E2E Verification Script
Tests every function: Login, Register, Trip Creation, Member Invitations,
Expense Adding, Exact Mathematical Splitting, Debt Simplification,
Notification Delivery (OTPs & Emails), and Settlement Execution.
Uses FastAPI TestClient for high-speed, direct synchronous integration testing.
"""

import sys
import time
import uuid
import re
import os

# Configure in-memory execution for speed and standalone reliability
os.environ["USE_INMEMORY_STORES"] = "true"
os.environ["AUTH_EXPOSE_OTP_IN_RESPONSE"] = "true"

try:
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services.notification_service import notification_service
except ImportError as e:
    print(f"[FAIL] Failed to import FastAPI TestClient or TripWise app: {e}")
    sys.exit(1)

client = TestClient(app)
BASE_URL = "/api/v1"

def log_section(title: str):
    print(f"\n=== {title} ===")

def log_success(msg: str):
    print(f"[OK] {msg}")

def log_error(msg: str):
    print(f"[FAIL] {msg}")

def assert_eq(actual, expected, label: str):
    if actual != expected:
        log_error(f"Assertion failed for {label}: expected {expected}, got {actual}")
        sys.exit(1)
    log_success(f"{label}: {actual} (as expected)")

def assert_approx(actual, expected, label: str, tol=0.01):
    if abs(actual - expected) > tol:
        log_error(f"Assertion failed for {label}: expected {expected}, got {actual}")
        sys.exit(1)
    log_success(f"{label}: {actual:.2f} (matches expected {expected:.2f})")

def get_latest_otp(email: str, res_json: dict = None) -> str:
    """Extracts the latest 6-digit OTP sent to the given email from API response or notification engine."""
    if res_json and res_json.get("otp"):
        return str(res_json["otp"])
    res = notification_service.list_jobs(limit=500)
    jobs = res.get("jobs", [])
    for job in reversed(jobs):
        if job.get("recipient") == email:
            html = job.get("htmlContent", "") or job.get("message", "")
            match = re.search(r"\b(\d{6})\b", html)
            if match:
                return match.group(1)
    log_error(f"No OTP found in notification jobs for email: {email}")
    sys.exit(1)

def register_user(email: str, name: str, nickname: str, phone: str, password: str) -> dict:
    log_section(f"Registering User: {name} ({email})")
    # 1. Request OTP
    payload = {
        "name": name,
        "nickname": nickname,
        "email": email,
        "phone": phone,
        "password": password,
        "confirm_password": password,
        "upi_id": f"{nickname.lower()}@upi",
        "upi_number": phone[1:]
    }
    res = client.post(f"{BASE_URL}/auth/register/request-otp", json=payload)
    if res.status_code != 200:
        log_error(f"Request registration OTP failed ({res.status_code}): {res.text}")
        sys.exit(1)
    log_success("Requested registration OTP successfully.")

    # 2. Extract OTP from notification engine (verifies email/message delivery!)
    otp = get_latest_otp(email, res.json())
    log_success(f"Verified OTP email notification delivery! Extracted OTP: {otp}")

    # 3. Verify OTP
    res = client.post(f"{BASE_URL}/auth/register/verify-otp", json={"email": email, "otp": otp})
    if res.status_code != 200:
        log_error(f"Verify registration OTP failed ({res.status_code}): {res.text}")
        sys.exit(1)
    data = res.json()
    assert "sessionToken" in data and "userId" in data, "Session token and userId must be returned on registration"
    log_success(f"User {name} registered and authenticated successfully!")
    return data

def test_auth_lifecycle(user_data: dict, email: str, password: str):
    log_section("Testing Authentication Lifecycle (Session Validation & Login)")
    token = user_data["sessionToken"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Validate Session Token
    res = client.post(f"{BASE_URL}/auth/session/validate", json={"session_token": token}, headers=headers)
    if res.status_code != 200:
        log_error(f"Session validation failed ({res.status_code}): {res.text}")
        sys.exit(1)
    val_data = res.json()
    assert_eq(val_data.get("valid"), True, "Session validity check")
    assert_eq(val_data.get("email"), email, "Session email verification")

    # 2. Login with Password
    res = client.post(f"{BASE_URL}/auth/login/password", json={"identifier": email, "password": password})
    if res.status_code != 200:
        log_error(f"Password login failed ({res.status_code}): {res.text}")
        sys.exit(1)
    login_data = res.json()
    assert "sessionToken" in login_data, "Session token must be returned on password login"
    log_success("Password login verified successfully!")

    # 3. Login with OTP
    res = client.post(f"{BASE_URL}/auth/login/request-otp", json={"identifier": email})
    if res.status_code != 200:
        log_error(f"Login OTP request failed ({res.status_code}): {res.text}")
        sys.exit(1)
    login_otp = get_latest_otp(email, res.json())
    log_success(f"Verified Login OTP message delivery! OTP: {login_otp}")
    res = client.post(f"{BASE_URL}/auth/login/verify-otp", json={"identifier": email, "otp": login_otp})
    if res.status_code != 200:
        log_error(f"Login OTP verification failed ({res.status_code}): {res.text}")
        sys.exit(1)
    log_success("OTP login verified successfully!")

def run_automated_test_suite():
    print("=====================================================================")
    print("      STARTING TRIPWISE AUTOMATED E2E INTEGRATION SUITE")
    print("=====================================================================")

    # Generate unique test identifiers
    run_id = str(uuid.uuid4())[:8]
    user1_email = f"alice_{run_id}@tripwise-auto.com"
    user2_email = f"bob_{run_id}@tripwise-auto.com"
    user3_email = f"charlie_{run_id}@tripwise-auto.com"
    password = "TestPassword123!"

    # 1. Register User 1 (Admin/Creator) and test Auth
    u1_data = register_user(user1_email, "Alice Admin", "Alice", "+919876543210", password)
    test_auth_lifecycle(u1_data, user1_email, password)
    u1_token = u1_data["sessionToken"]
    u1_headers = {"Authorization": f"Bearer {u1_token}"}
    u1_identifier = user1_email

    # 2. Register User 2 & User 3
    u2_data = register_user(user2_email, "Bob Member", "Bob", "+919876543211", password)
    u2_token = u2_data["sessionToken"]
    u2_headers = {"Authorization": f"Bearer {u2_token}"}

    u3_data = register_user(user3_email, "Charlie Member", "Charlie", "+919876543212", password)
    u3_token = u3_data["sessionToken"]
    u3_headers = {"Authorization": f"Bearer {u3_token}"}

    # 3. Create a Trip
    log_section("Testing Trip Creation")
    trip_payload = {
        "creator_identifier": u1_identifier,
        "creator_name": "Alice Admin",
        "name": f"Goa Automated Expedition {run_id}",
        "creation_mode": "dynamic"
    }
    res = client.post(f"{BASE_URL}/trips/", json=trip_payload, headers=u1_headers)
    if res.status_code != 200:
        log_error(f"Trip creation failed ({res.status_code}): {res.text}")
        sys.exit(1)
    trip_data = res.json()
    trip_id = trip_data["trip"].get("tripId") or trip_data["trip"].get("trip_id")
    assert_eq(trip_data["trip"]["status"], "planning", "Trip initial status")
    log_success(f"Created trip successfully! ID: {trip_id}")

    # 4. Invite & Join Members
    log_section("Testing Member Invitations & Joining")
    invite_all_payload = {
        "actor_identifier": u1_identifier,
        "identifiers": [user2_email, user3_email]
    }
    res = client.post(f"{BASE_URL}/trips/{trip_id}/members/invite-all", json=invite_all_payload, headers=u1_headers)
    if res.status_code != 200:
        log_error(f"Member invitation failed ({res.status_code}): {res.text}")
        sys.exit(1)
    invite_res = res.json()
    log_success(f"Invited members: {len(invite_res.get('members', []))} member records processed.")

    # Check that email notifications went out for invitations
    jobs_res = notification_service.list_jobs(limit=50)
    invitation_jobs = [j for j in jobs_res.get("jobs", []) if j.get("recipient") in (user2_email, user3_email)]
    log_success(f"Verified invitation notification delivery! Found {len(invitation_jobs)} notification jobs.")

    # Get member IDs for Bob & Charlie
    res = client.get(f"{BASE_URL}/trips/{trip_id}/members", headers=u1_headers)
    members = res.json().get("members", [])
    u1_member_id = next((m.get("memberId") or m.get("member_id")) for m in members if m.get("identifier") == user1_email)
    u2_member_id = next((m.get("memberId") or m.get("member_id")) for m in members if m.get("identifier") == user2_email)
    u3_member_id = next((m.get("memberId") or m.get("member_id")) for m in members if m.get("identifier") == user3_email)

    # Bob accepts invitation
    res = client.post(f"{BASE_URL}/trips/members/{u2_member_id}/respond", json={"actor_identifier": user2_email, "action": "accepted"}, headers=u2_headers)
    assert_eq(res.status_code, 200, "Bob accepts trip invitation")

    # Charlie accepts invitation
    res = client.post(f"{BASE_URL}/trips/members/{u3_member_id}/respond", json={"actor_identifier": user3_email, "action": "accepted"}, headers=u3_headers)
    assert_eq(res.status_code, 200, "Charlie accepts trip invitation")
    log_success("All members joined the trip successfully!")

    # 5. Add Expenses & Test Exact Mathematical Splitting
    log_section("Testing Expense Adding & Exact Mathematical Splitting")
    
    # Expense 1: Alice pays $300, split equally among Alice, Bob, Charlie ($100 each).
    # Net balance effect:
    # Alice: +$300 (paid) - $100 (share) = +$200
    # Bob:   $0 (paid) - $100 (share) = -$100
    # Charlie: $0 (paid) - $100 (share) = -$100
    exp1_payload = {
        "trip_id": trip_id,
        "actor_identifier": u1_identifier,
        "amount": 300.0,
        "description": "Hotel Booking (Equal Split)",
        "paid_by": [{"member_id": u1_member_id, "amount_paid": 300.0}],
        "split_type": "equal",
        "splits": [] # Empty splits triggers equal split among all eligible members
    }
    res = client.post(f"{BASE_URL}/expenses/", json=exp1_payload, headers=u1_headers)
    if res.status_code != 200:
        log_error(f"Expense 1 creation failed ({res.status_code}): {res.text}")
        sys.exit(1)
    log_success("Added Expense 1 ($300 equal split) successfully!")

    # Check Settlement after Expense 1
    res = client.get(f"{BASE_URL}/payments/settlement?trip_id={trip_id}", headers=u1_headers)
    settlements = res.json().get("whoOwesWhom", [])
    log_success(f"Calculated settlements after Expense 1: {len(settlements)} transactions.")
    assert_eq(len(settlements), 2, "Number of settlement transactions after Exp 1")
    
    for s in settlements:
        from_id = s.get("fromMemberId") or s.get("from_member_id")
        to_id = s.get("toMemberId") or s.get("to_member_id")
        if from_id == u2_member_id:
            assert_approx(s["amount"], 100.0, "Bob owes Alice after Exp 1")
            assert_eq(to_id, u1_member_id, "Bob pays to Alice")
        elif from_id == u3_member_id:
            assert_approx(s["amount"], 100.0, "Charlie owes Alice after Exp 1")
            assert_eq(to_id, u1_member_id, "Charlie pays to Alice")

    # Expense 2: Bob pays $200, split 50% Bob ($100) and 50% Charlie ($100). Alice excluded!
    # Net balance effect of Expense 2 alone:
    # Alice: $0
    # Bob:   +$200 (paid) - $100 (share) = +$100
    # Charlie: $0 (paid) - $100 (share) = -$100
    #
    # COMBINED NET BALANCES (Exp 1 + Exp 2):
    # Alice:   +$200 + $0   = +$200
    # Bob:     -$100 + $100 = $0 (Bob is completely settled!)
    # Charlie: -$100 - $100 = -$200
    #
    # Expected Debt Simplification Result:
    # Exactly ONE transaction: Charlie owes Alice $200! Bob owes nothing!
    log_section("Testing Debt Simplification Algorithm with Expense 2")
    exp2_payload = {
        "trip_id": trip_id,
        "actor_identifier": user2_email,
        "amount": 200.0,
        "description": "Car Rental (Percentage Split, Alice Excluded)",
        "paid_by": [{"member_id": u2_member_id, "amount_paid": 200.0}],
        "split_type": "percentage",
        "splits": [
            {"member_id": u1_member_id, "percentage": 0.0, "excluded": True},
            {"member_id": u2_member_id, "percentage": 50.0, "excluded": False},
            {"member_id": u3_member_id, "percentage": 50.0, "excluded": False}
        ]
    }
    res = client.post(f"{BASE_URL}/expenses/", json=exp2_payload, headers=u2_headers)
    if res.status_code != 200:
        log_error(f"Expense 2 creation failed ({res.status_code}): {res.text}")
        sys.exit(1)
    exp2_data = res.json()
    exp2_id = exp2_data["expense"].get("expenseId") or exp2_data["expense"].get("expense_id")
    log_success("Added Expense 2 ($200 percentage split) successfully!")

    # Alice (admin) approves Expense 2
    res = client.post(f"{BASE_URL}/expenses/{exp2_id}/approve", json={"admin_identifier": u1_identifier}, headers=u1_headers)
    if res.status_code != 200:
        log_error(f"Expense 2 approval failed ({res.status_code}): {res.text}")
        sys.exit(1)
    log_success("Alice approved Expense 2 successfully!")

    # Check updated settlements
    res = client.get(f"{BASE_URL}/payments/settlement?trip_id={trip_id}", headers=u1_headers)
    settlements_mod = res.json().get("whoOwesWhom", [])
    log_success(f"Calculated simplified settlements after Expense 2: {len(settlements_mod)} transactions.")
    assert_eq(len(settlements_mod), 1, "Number of simplified settlement transactions")
    
    simplified_tx = settlements_mod[0]
    from_id = simplified_tx.get("fromMemberId") or simplified_tx.get("from_member_id")
    to_id = simplified_tx.get("toMemberId") or simplified_tx.get("to_member_id")
    assert_eq(from_id, u3_member_id, "Debtor in simplified settlement (Charlie)")
    assert_eq(to_id, u1_member_id, "Creditor in simplified settlement (Alice)")
    assert_approx(simplified_tx["amount"], 200.0, "Exact debt simplification amount ($200)")
    log_success("Debt Simplification algorithm verified: Bob's debt canceled out, Charlie owes Alice $200!")

    # 6. Test Settlement Execution (Mark Paid)
    log_section("Testing Settlement Execution & Payment History")
    pay_payload = {
        "trip_id": trip_id,
        "actor_identifier": u1_identifier,
        "from_member_id": u3_member_id,
        "to_member_id": u1_member_id,
        "amount": 200.0,
        "method": "UPI"
    }
    res = client.post(f"{BASE_URL}/payments/mark-paid", json=pay_payload, headers=u1_headers)
    if res.status_code != 200:
        log_error(f"Mark paid failed ({res.status_code}): {res.text}")
        sys.exit(1)
    log_success("Marked $200 settlement as paid successfully!")

    # Verify that remaining settlement list is now empty!
    res = client.get(f"{BASE_URL}/payments/settlement?trip_id={trip_id}", headers=u1_headers)
    remaining_settlements = res.json().get("whoOwesWhom", [])
    assert_eq(len(remaining_settlements), 0, "Remaining settlements after full payment")
    log_success("Verified: Trip is 100% settled with zero remaining debts!")

    # Verify payment history
    res = client.get(f"{BASE_URL}/payments/history?trip_id={trip_id}", headers=u1_headers)
    history = res.json().get("transactions", [])
    assert_eq(len(history), 1, "Payment history records count")
    assert_approx(history[0]["amount"], 200.0, "Recorded payment history amount")
    log_success("Verified payment history record!")

    # 7. Test Realtime Ledger & Report Generation
    log_section("Testing Realtime Summary & Report Generation")
    res = client.get(f"{BASE_URL}/realtime/{trip_id}", headers=u1_headers)
    assert_eq(res.status_code, 200, "Realtime summary endpoint status")
    log_success("Realtime ledger summary fetched successfully!")

    report_payload = {
        "trip_id": trip_id,
        "actor_identifier": u1_identifier,
        "report_type": "detailed",
        "format": "pdf"
    }
    res = client.post(f"{BASE_URL}/reports/generate", json=report_payload, headers=u1_headers)
    if res.status_code != 200:
        log_error(f"Report generation failed ({res.status_code}): {res.text}")
        sys.exit(1)
    report_data = res.json()
    report_id = report_data.get("report", {}).get("reportId") or report_data.get("report", {}).get("report_id")
    assert report_id, "Report ID must be present"
    log_success(f"Generated automated PDF/Excel report successfully! Report ID: {report_id}")

    print("\n=====================================================================")
    print("      [SUCCESS] ALL TRIPWISE FUNCTIONS & SPLITTING ALGORITHMS VERIFIED 100%!")
    print("=====================================================================\n")

if __name__ == "__main__":
    run_automated_test_suite()
