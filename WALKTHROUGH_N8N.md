# How to Set Up Your Automated Business Engine (n8n Walkthrough)

This guide walks you through setting up the 5 "Master Flows" that power MODYFIRE. Think of each flow as a department in your company that runs 24/7 without you.

## 🟢 Prerequisites
1.  **n8n Installed:** You must have n8n running (either self-hosted or n8n cloud).
2.  **API Keys Ready:**
    *   `AUTH_SECRET_TOKEN`: A secret password you created (e.g., `my-secret-token-123`). This keeps your webhooks safe.
    *   **Google Sheets / Gmail / Drive:** For logging data and sending emails.
    *   **Stripe:** For payments.
    *   **Instantly.ai:** For sending cold emails (Growth flow).
    *   **Kling / ElevenLabs / Gemini:** For AI content generation.

---

## 🚀 Step 1: Growth & Onboarding (Begin Here!)
**Why?** You can't run a business without customers. This flow handles new user signups and sales outreach.

**File:** `n8n/consolidated/group_2_growth_onboarding.json`

### **How to Import & Configure:**
1.  **Open n8n** in your browser.
2.  Click **"Add Workflow"** (top right).
3.  Click the **three dots (...)** in the top right -> **"Import from File"**.
4.  Select `group_2_growth_onboarding.json`.
5.  **Configure Credentials (Red Warning Nodes):**
    *   **Authentication:** You will see nodes with warnings. Double click them.
    *   **Gmail Node:** Select "Credential" -> "Create New" -> Connect your Google Account.
    *   **Instantly.ai Node:** Double click -> Under Headers -> Replace `YOUR_INSTANTLY_API_KEY` with your actual key.
    *   **Google Sheets Node:** Replace `YOUR_SHEET_ID` with the ID from your Google Sheet URL (the part between `/d/` and `/edit`).
6.  **Set Environment Variables:**
    *   Go to n8n Settings or your `.env` file for n8n.
    *   Add `AUTH_SECRET_TOKEN=your-secret-password`.
7.  **Activate:** Toggle the "Active" switch to ON (top right).

**What it does now:**
*   When a user signs up on your site, they get a "Welcome" email from "Kai" (Marketing persona).
*   Every morning at 9 AM, it finds leads and adds them to your Instantly.ai campaign automatically.

---

## 💰 Step 2: Revenue Ledger (The Bank)
**Why?** You need to get paid and track credits so you don't go broke on API fees.

**File:** `n8n/consolidated/group_1_revenue_ledger.json`

### **How to Configuration:**
1.  **Import** the file as before.
2.  **Stripe Webhook Node:**
    *   Copy the "Production URL" shown in the node.
    *   Go to your **Stripe Dashboard** -> Developers -> Webhooks -> Add Endpoint.
    *   Paste the URL. Select event: `checkout.session.completed`.
3.  **Update App Balance Node:**
    *   This node talks back to your Python app to say "Give User 100 credits".
    *   Ensure `APP_URL` environment variable is set to your app's URL (e.g. `https://modyfire.com`).

---

## 🧠 Step 3: Content Engine (The Product)
**Why?** This *is* the app. It makes the flashcards and summaries.

**File:** `n8n/consolidated/group_3_content_engine.json`

### **How to Configuration:**
1.  **Import** the file.
2.  **Check API Keys:** Ensure your Gemini/OpenAI credentials are connected in n8n.
3.  **Test:**
    *   Click "Execute Workflow".
    *   Upload a file in your App Dashboard.
    *   Watch the green success bubbles pop up in n8n!

---

## 🛡️ Step 4: Security & Support (The Bodyguard)
**Why?** If the server crashes, you need to know. If a user asks for a refund, you need to know.

**File:** `n8n/consolidated/group_4_security_support.json`

### **How to Configuration:**
1.  **Import** the file.
2.  **WhatsApp Node:**
    *   Connect your Meta/Facebook Business account to get a Phone ID.
    *   Replace `YOUR_WHATSAPP_NUMBER`.
3.  **Kai AI Agent Node:**
    *   This is already set up with a prompt. It works automatically when you connect your Gmail.

---

## 📢 Step 5: Marketing & Outreach (The Bullhorn)
**Why?** To grow viral on TikTok/Reels without doing the work.

**File:** `n8n/consolidated/group_5_marketing_content.json`

### **How to Configuration:**
1.  **Import** the file.
2.  **Weekly Trigger:** It's set to Monday at 10 AM. You can change this schedule.
3.  **Creative APIs:**
    *   **ElevenLabs:** Enter your API Key for voice generation.
    *   **Kling AI:** Enter your Key for video generation.
4.  **Result:** Every Monday, you'll get an email with a ready-to-post video file attached.

---

### 🌟 Summary Checklist
- [ ] Install n8n.
- [ ] Create `AUTH_SECRET_TOKEN`.
- [ ] Import **Group 2** (Growth) -> Connect Gmail/Instantly.
- [ ] Import **Group 1** (Revenue) -> Connect Stripe.
- [ ] Import **Group 3** (Content) -> Connect Gemini.
- [ ] **Activate All Workflows.**

You now have a fully automated business!
