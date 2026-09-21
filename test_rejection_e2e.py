import os
import time
import requests
from playwright.sync_api import sync_playwright, expect

def run_rejection_test():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            # 1. Login
            page.goto("http://localhost:3000/login")
            page.fill("input[type=email]", "e2e_test@seva.gov")
            page.fill("input[type=password]", "password123")
            page.click("button[type=submit]")
            page.wait_for_url("**/dashboard**", timeout=10000)
            
            # 2. Create Application via Chat
            page.fill("input[type=text]", "I want to apply for income certificate")
            page.click("button:has(svg.lucide-send)")
            page.wait_for_timeout(5000) # Wait for AI
            
            # 3. Upload Document
            file_input = page.locator("input[type=file]")
            file_input.set_input_files("/Users/anseljustin/.gemini/antigravity-ide/scratch/seva-ai/test_data/test.pdf")
            page.wait_for_timeout(5000)
            
            # 4. Consent and Submit
            page.fill("input[type=text]", "Yes, I consent to submit my application")
            page.click("button:has(svg.lucide-send)")
            page.wait_for_timeout(8000)
            
            # Go to applications
            page.goto("http://localhost:3000/applications")
            page.locator("text=Income Certificate").first.click()
            page.wait_for_url("**/applications/**")
            
            # The application might still be in CONSENT_REQUIRED if chat didn't fully submit it,
            # Let's check if there's an "Approve & Submit" button on the preview
            if page.locator("button:has-text('Approve & Submit')").is_visible():
                page.click("button:has-text('Approve & Submit')")
                page.wait_for_timeout(3000)
            
            # Extract government reference
            gov_ref = page.locator("text=REV-").first.inner_text()
            print(f"Government Reference: {gov_ref}")
            
            # Advance to UNDER_REVIEW
            res = requests.post(f"http://localhost:8000/api/mock/revenue/admin/advance-status/{gov_ref}")
            print("Advanced to UNDER_REVIEW:", res.json())
            
            # Advance to REJECTED
            res = requests.post(f"http://localhost:8000/api/mock/revenue/admin/advance-status/{gov_ref}?reject=true")
            print("Advanced to REJECTED:", res.json())
            
            # Refresh page
            page.reload()
            page.wait_for_timeout(2000)
            
            # Verify UI shows Rejection
            expect(page.locator("text=REJECTED")).to_be_visible()
            
            print("REJECTION TEST PASSED")
            
        except Exception as e:
            print("REJECTION TEST FAILED:", str(e))
        finally:
            browser.close()

if __name__ == "__main__":
    run_rejection_test()
