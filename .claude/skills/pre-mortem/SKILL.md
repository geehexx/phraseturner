---
name: pre-mortem
description: "Risk analysis workflow that imagines a future failure and works backwards to identify causes. Use before high-stakes deployments, demos, or decisions to surface risks that optimism bias would otherwise hide. Particularly valuable before the May 8 Jen Gennai demo and May 14 company leaders demo — any time you feel confident is exactly when you need a pre-mortem most. Produces a Likelihood × Impact risk register with prioritised mitigations and a Go/No-Go recommendation. Covers technical, process, external, and security risk categories with cv-builder-specific mitigation playbooks. Activates on: pre-mortem, risk analysis, what could go wrong, failure analysis, risk assessment, identify risks, demo risk, deployment risk, go no-go decision, risk register, mitigation plan, contingency planning."
metadata:
  category: planning
  complexity: 2
  activation_examples:
    - "pre-mortem on the May 8 demo — what could go wrong?"
    - "risk analysis before the ElastiCache Redis deployment"
    - "what could go wrong with the auth simplification changes?"
    - "failure analysis for the vendor enrichment pipeline"
    - "identify risks before the DNS cutover"
  related_steering:
    - spec-creation-guide
    - orchestration
---

# Pre-Mortem

Risk analysis workflow that imagines a future failure and works backwards to identify causes. Surfaces risks that optimism bias would otherwise hide, before it's too late to mitigate them.

## Why Pre-Mortems Work

The pre-mortem technique (Klein, 1989) works by bypassing optimism bias. Instead of asking "what might go wrong?" (which feels pessimistic and is resisted), it asks "it's the day after and it failed — why?" This framing makes it psychologically safe to identify risks and produces more comprehensive risk lists than traditional risk assessment.

## When to Use

- Before the May 8 Jen Gennai demo (HARD DEADLINE)
- Before the May 14 company leaders demo (HARD DEADLINE)
- Before any production deployment (CDK deploy, DNS cutover, ECS update)
- Before a major code change (auth simplification, async migration)
- Before a significant decision (new vendor, new technology, new process)
- Any time you feel "this will definitely work" — that's when you need a pre-mortem most

## Step 1 — Imagine the Failure

Set the scene explicitly. The more vivid the failure scenario, the more risks you'll surface.

**Template:**
> "It's [date + 1 day] and [the thing] has failed. The [demo/deployment/decision] did not go as planned. What went wrong?"

**cv-builder-specific failure scenarios:**

For the May 8 demo:
> "It's May 9, 2026. The Jen Gennai demo failed. She left unimpressed and we didn't get the contract. What went wrong?"

For a production deployment:
> "It's [date + 1]. The CDK deployment to production failed. The site is down and users can't access cv-builder. What went wrong?"

For an auth change:
> "It's [date + 1]. The auth simplification broke login for all users. The security audit found a vulnerability. What went wrong?"

## Step 2 — Brainstorm Failure Causes

Generate failure causes across all relevant categories. Don't filter — capture everything, even unlikely scenarios.

**cv-builder Risk Categories:**

### Technical Risks
- **Search quality**: Results are wrong, irrelevant, or missing key vendors
- **Performance**: Endpoint too slow (>500ms), page load too slow (>4s)
- **Authentication**: Login fails, session expires during demo, rate limit hit
- **Data**: Vendor data is stale, missing, or incorrect
- **Infrastructure**: ECS service down, database connection failed, CDK deploy failed
- **Output**: rendercv template error, PDF generation failure, DOCX corruption

### Process Risks
- **Preparation**: Demo not rehearsed, staging site not verified, backup not prepared
- **Communication**: Wrong audience expectations, wrong demo scenario, wrong talking points
- **Dependencies**: Third-party service down (Linear, CodeRabbit, Slack), API key expired

### External Risks
- **Connectivity**: Internet down at demo location, VPN issues, firewall blocking staging
- **Environment**: Wrong browser, wrong device, screen sharing not working
- **Timing**: Demo runs over time, Q&A takes too long, technical issues eat into demo time

### Security Risks
- **Credentials**: Staging credentials exposed, API key leaked in demo
- **Data**: PII visible in demo, wrong organisation's data shown
- **Compliance**: Demo reveals a compliance gap

## Step 3 — Assess Likelihood × Impact

For each identified risk, assess:
- **Likelihood**: 1 (very unlikely) to 5 (very likely)
- **Impact**: 1 (minor inconvenience) to 5 (catastrophic failure)
- **Priority**: Likelihood × Impact (1-25)

```markdown
| Risk | Likelihood | Impact | Priority | Mitigation |
|------|-----------|--------|----------|------------|
| Staging site down during demo | 2 | 5 | 10 | Prepare screenshots as backup |
| Search returns wrong results | 3 | 4 | 12 | Verify canonical query day before |
| Login rate limit hit | 3 | 3 | 9 | Use fresh browser session |
| Internet connectivity issue | 2 | 5 | 10 | Download demo video as backup |
| Demo runs over time | 4 | 2 | 8 | Rehearse with timer |
```

**Priority thresholds:**
- Priority ≥15: Critical — must mitigate before proceeding
- Priority 10-14: High — should mitigate
- Priority 5-9: Medium — monitor and have contingency
- Priority <5: Low — accept the risk

## Step 4 — Mitigation Plan

For each high-priority risk, define a specific mitigation:

**Mitigation types:**
- **Prevent**: Change the plan to eliminate the risk
- **Reduce**: Take action to lower likelihood or impact
- **Contingency**: Prepare a backup plan if the risk materialises
- **Accept**: Acknowledge the risk and proceed (for low-priority risks)

**cv-builder Demo Mitigation Playbook:**

| Risk | Mitigation | Owner | Deadline |
|------|-----------|-------|----------|
| Staging site down | Prepare screenshots of each demo step | Andrew | Day before |
| Search returns wrong results | Run canonical query and verify results | Andrew | Day before |
| Login rate limit | Use fresh browser session, clear cookies | Andrew | Day of |
| Internet connectivity | Download demo video as backup | Andrew | Day before |
| Demo runs over time | Rehearse with timer, cut comparison section if needed | Andrew | Day before |
| Credentials exposed | Use staging credentials only, never production | Andrew | Always |

## Pre-Mortem Report Template

```markdown
## Pre-Mortem Report
Date: {date}
Subject: {what is being assessed}
Failure scenario: "{vivid failure description}"

### Risk Register

#### Critical Risks (Priority ≥15)
| Risk | L | I | P | Mitigation | Owner | Deadline |
|------|---|---|---|-----------|-------|----------|
| {risk} | {1-5} | {1-5} | {L×I} | {action} | {person} | {date} |

#### High Risks (Priority 10-14)
[same format]

#### Medium Risks (Priority 5-9)
[same format]

### Mitigation Actions
- [ ] {action 1} — {owner} — by {date}
- [ ] {action 2} — {owner} — by {date}

### Residual Risks (accepted)
- {risk}: accepted because {reason}

### Go/No-Go Decision
Based on this pre-mortem:
- [ ] All Critical risks have mitigations in place
- [ ] All High risks have mitigations or contingencies
- Recommendation: {GO / NO-GO / CONDITIONAL GO with conditions}
```

## cv-builder-Specific Risk Checklist

Before any production deployment, verify:
- [ ] `cdk diff` shows only expected changes
- [ ] Staging deployment tested and verified
- [ ] Rollback plan documented (previous task definition ARN, previous image tag)
- [ ] Monitoring alarms configured
- [ ] On-call contact available during deployment window

Before any demo:
- [ ] Staging site verified with `web-browse` skill
- [ ] Canonical search query returns expected results
- [ ] Comparison table loads for top 3 vendors
- [ ] Screenshots prepared as backup
- [ ] Rehearsal completed with timer

## References

- `product.md` — Business context, deadlines, demo scenario
- `presentation-prep` skill — Demo preparation workflow
- `web-browse` skill — Verify staging site before demo
- `mcp_basic_memory_write_note` — Store risk register for future reference
