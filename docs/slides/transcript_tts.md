# PA-Trace Director's Script (For Minimax TTS)

> **Usage:** Go to [Minimax Audio TTS](https://www.minimax.io/audio/text-to-speech) (Use **Speech-2.5-HD** or **Speech 2.6** if available).
> 
> **Voice Selection:** Based on community recommendations for tech demos, choose from the **"Professional"** or **"Expressive"** engine categories. Look for voices like **"Tech Explainer"**, **"Corporate Presenter"**, or any calm, authoritative mid-range English male/female voice. Uncheck any "hyper-emotional" tags.
>
> **Minimax Tag Guide:**
> - **Pauses:** Use `<#seconds#>` anywhere you need a pause. For example, `<#1#>` creates a 1-second pause, and `<#15#>` creates a 15-second pause!
> - **Sounds:** Use parenthetical tags like `(breath)`, `(sighs)`, or `(clear-throat)` to make the AI sound more human.
>
> Below is the unified transcript perfectly paced for your screen recording. Paste everything inside the "TEXT BLOCK" directly into Minimax.

---

### TEXT BLOCK

Hi, I'm Eido. Prior authorization costs US healthcare thirty-five billion dollars a year. <#0.5#> For imaging orders, clinicians spend up to forty-five minutes per case extracting evidence from notes and cross-referencing payer criteria. <#0.5#> PA-Trace automates that. 

<#1.5#> (breath) 

Here's how it works. <#0.5#> MedGemma four-B runs entirely on-device. <#0.5#> It reads the clinic note, extracts structured facts, symptom duration, treatments, red flags, and every field must include an exact quote. <#0.5#> A baseline keyword detector runs alongside as a safety net, and a rule-based checklist engine produces the final decision: <#0.5#> met, <#0.3#> not met, <#0.3#> or unknown.

<#1.5#> (breath) 

Here's a real output for case one: eight weeks of back pain, ibuprofen, naproxen, six weeks of physical therapy. <#0.5#> Every fact linked to the source text.

<#1.5#> 

But the real magic is the evidence visualization. <#0.5#> Watch, the system scans the note and highlights every piece of evidence.

<#15#> (breath) 

Each highlight traces to an exact character range. <#0.5#> The evidence table populates as highlights appear. <#0.5#> And at the bottom, status is MET. <#0.5#> Six weeks of conservative care documented.

<#1.5#> (breath) 

Now case two: <#0.5#> only three weeks of back pain, no physical therapy. <#0.5#> Not enough evidence.

<#1.5#> 

Status: UNKNOWN. <#1#> PA-Trace doesn't guess. <#0.5#> It abstains and flags for human review.

<#1.5#> (breath) 

Eleven synthetic cases. <#0.5#> One hundred percent decision accuracy. <#0.5#> One hundred percent provenance validity. <#0.5#> One hundred percent abstention precision. <#1#> Field extraction isn't perfect yet, but the system is designed so that gaps trigger abstention, not wrong decisions.

<#1.5#> (breath) 

PA-Trace: <#0.5#> MedGemma four-B, fully on-device, no PHI exposure, evidence-traced prior-auth drafts. <#1#> When it doesn't have enough evidence, it tells you. <#0.5#> Code is open source on GitHub. <#0.5#> Thank you for watching.

---

### STAGE DIRECTIONS REFERENCE (Do NOT Paste)
- **0.00** "Hi, I'm Eido..." → VS Code `1-intro.md`
- *[1.5s Pause]* → Switch to `2-architecture.md`
- **0.20** "Here's how it works..." → VS Code `2-architecture.md`
- *[1.5s Pause]* → Switch to Terminal
- **0.40** "Here's a real output..." → Run `cat runs/eval/case_01/packet.json | head -30`
- *[1.5s Pause]* → Switch browser, click "Analyze"
- **0.50** "But the real magic..." → Browser `highlights.html`
- *[15s Pause]* → Let highlight animation scan finish, scroll to table
- **1.05** "Each highlight traces..." → Still in browser showing table
- *[1.5s Pause]* → Switch to Terminal
- **1.50** "Now case two..." → Run `cat runs/eval/case_02/packet.json | head -20`
- *[1.5s Pause]* → Terminal
- **2.00** "Status: UNKNOWN..." → Run `cat runs/eval/case_02/checklist.json`
- *[1.5s Pause]* → Terminal
- **2.15** "Eleven synthetic..." → Run `cat runs/eval/metrics.json`
- *[1.5s Pause]* → Switch to VS Code `3-closing.md`
- **2.40** "PA-Trace: MedGemma..." → VS Code `3-closing.md`
