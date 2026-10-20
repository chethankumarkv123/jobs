# Antigravity Agent Instructions — Personalized Job Finder

## Mission
Run a reliable daily job search for roles that fit the candidate profile below. Find real, currently open vacancies; verify them; rank them transparently; and produce a concise report with direct application links. Do not invent jobs, posting dates, salary data, hiring managers, employer URLs, or remote-work eligibility.

## Candidate profile (source: supplied resume)
- Current employer: LTIMindtree, Bengaluru, India.
- Total experience: 4+ years, from April 2022 to present.
- Current/recent role: Azure Cloud Engineer, June 2024–present.
- Previous role: Desktop & Linux Support Engineer, April 2022–June 2024.
- Primary target: Azure Cloud / Infrastructure / DevOps / Cloud Operations / Cloud Automation / Platform Engineering.
- Secondary targets: Linux Cloud Engineer, SRE, Kubernetes/AKS, DevSecOps, Vulnerability Management / Cloud Security Operations, Infrastructure Automation.
- Cloud platforms: Microsoft Azure, AWS, GCP.
- Azure: Virtual Machines (Linux/Windows), AKS, App Service, Key Vault, Storage, VNets, subnets, NSGs, UDRs, Load Balancers, Application Gateway, RBAC, Azure Monitor, Log Analytics, backup/recovery and disaster recovery.
- Infrastructure automation: Terraform, Ansible, Python, Bash, shell scripting, GitHub Actions, Azure DevOps, Git, YAML, Groovy.
- Containers: Docker, AKS/Kubernetes, microservices.
- Linux/platform: RHEL, Ubuntu, CentOS, Windows Server, patching, server lifecycle management, golden images, SSH/access hardening, configuration drift and baseline enforcement.
- Security/compliance: Qualys, BigFix, CIS benchmarks, vulnerability remediation, CVE triage, Microsoft Defender for Cloud, security hardening, DevSecOps.
- Operations: ServiceNow, P1/P2 incidents, RCA, post-incident reports, on-call support, SLA/MTTR improvement, Grafana and monitoring.
- Resume-backed impact: supported production environments with 99.9% uptime; secured/connectivity configuration for 100+ servers; standardized automation/configuration for 100+ Linux servers; delivered a $2.5M Linux MDM SaaS platform from PoC to production as sole technical owner; achieved 66% production server compliance in one overnight operational window; recurring Azure resource reviews and cost optimization.
- Certification/training: AZ-104 Microsoft Azure Administrator is in progress. Do not represent it as completed.
- Education: BCA and Diploma in Computer Science. Do not make education or backlog assumptions; follow the startup exception below.

Use these facts to assess relevance. Do not claim the candidate has skills or achievements not listed above. Treat job-title seniority flexibly: the candidate has 4+ years overall and Azure Cloud Engineer experience since June 2024, so distinguish total IT experience from time specifically in a cloud-engineering title.

## Location priority — mandatory
1. **Bengaluru/Bangalore, India — highest priority:** onsite, hybrid, and remote roles based in Bengaluru.
2. **Anywhere in India:** onsite, hybrid, and remote roles in any Indian city.
3. **Worldwide remote:** fully remote roles that explicitly allow candidates who reside in India and can employ them compliantly.
- Do not treat “remote” as automatically worldwide. Check eligible countries, location restrictions, payroll/employment restrictions, and work authorization.
- Exclude roles requiring relocation outside India unless the vacancy explicitly offers relocation and the role is otherwise a good match.
- Location priority affects ranking, not eligibility: strong India-eligible worldwide remote roles remain in scope.

## Experience and eligibility filters
- Target roles asking for approximately **3–6 years** of relevant experience; prioritize 4–5 years.
- Exclude roles that explicitly require 7+ years as a hard minimum. If a role says 5+ years, keep it only if the actual requirements are otherwise a close fit and flag the experience gap.
- Do not reject a role solely because its title says Senior if the listed experience and responsibilities fit.
- For startup roles, **ignore degree, college, and backlog requirements entirely**. Do not use them to reject or down-rank a startup vacancy.
- For established employers, record any explicit education requirement, but do not infer an unmentioned backlog or assume the candidate is ineligible.
- Do not reject solely because AZ-104 is in progress; do not claim certification is complete.
- Include direct-employer roles. Avoid recruitment agencies/consultancies unless the actual hiring employer is identified and the vacancy is verifiable.

## Job-source order
Search these sources every run, within practical rate and access limits:

### Priority 1 — official company career pages
This is the preferred source and preferred application route. Search official career sites for Bengaluru companies first, then other Indian employers, then global companies with India-eligible remote roles. Include established companies, product/SaaS companies, cloud/platform companies, cybersecurity firms, and startups.
- Aim for at least 70% of confirmed listings to be found on or verified against official employer career pages when enough qualifying jobs exist.
- Record the exact official job/application URL.
- A search-engine snippet is not sufficient proof that a role is still open.

### Priority 2 — Wellfound
Use Wellfound heavily for Bengaluru startups, Indian startups, SaaS, AI, developer tools, cloud infrastructure, platform engineering, and cybersecurity.
- Startup degree/backlog exception applies.
- Prefer direct company application pages when available.

### Priority 3 — LinkedIn Jobs
Run LinkedIn searches daily for the keywords below. Use past-24-hours filters where available. Use LinkedIn for discovery, then verify on the employer's official careers page whenever possible.
- Store the LinkedIn listing URL and official application URL separately.
- Do not claim that LinkedIn search was exhaustively checked if access restrictions prevent that.

### Priority 4 — additional job boards
Use Naukri, Indeed India, Cutshort, Instahyre, Y Combinator jobs, Startup.jobs, Himalayas, We Work Remotely, Remote OK, Jobicy, Working Nomads, Authentic Jobs, and Careerjet as supplementary discovery sources. Verify the employer and vacancy wherever possible.
- Respect site terms, robots.txt, rate limits, and access controls.
- Do not bypass logins, paywalls, CAPTCHAs, or technical protections. Prefer public pages, official APIs, feeds, or permitted search interfaces.

## Search keyword groups
Run multiple targeted searches rather than one overly broad query:
1. Azure Cloud Engineer; Azure Infrastructure Engineer; Azure Administrator.
2. Azure DevOps Engineer; DevOps Engineer; Cloud DevOps Engineer.
3. Cloud Operations Engineer; Cloud Support Engineer; Production Engineer.
4. Platform Engineer; Infrastructure Engineer; Infrastructure Automation Engineer.
5. Kubernetes Engineer; AKS Engineer; Container Platform Engineer.
6. Linux Cloud Engineer; Linux Systems Engineer; Linux Infrastructure Engineer.
7. Terraform Engineer; Cloud Automation Engineer; IaC Engineer.
8. Site Reliability Engineer / SRE, where Linux, cloud, automation, monitoring, and incident response are relevant.
9. DevSecOps Engineer; Cloud Security Engineer; Vulnerability Management Engineer, where infrastructure automation and cloud operations are central.
10. Remote Azure Engineer; Remote DevOps Engineer; Remote Cloud Infrastructure Engineer (India-eligible).

Do not include software-development-only jobs that require extensive application coding unrelated to the candidate's infrastructure profile, nor pure desktop/helpdesk jobs unless they have a substantial Linux/cloud/automation component.

## Freshness — strict
- The main confirmed report may contain only jobs originally posted within the last **24 hours**.
- Verify the original posting date from the employer or a reliable listing. Distinguish original posting date from “updated,” “reposted,” “refreshed,” and search-engine indexing dates.
- If the original posting date cannot be established, put the job in a separate **Date Unverified — Review Manually** section, not the confirmed results.
- If a vacancy is closed, expired, or no longer present on the employer's career site, do not list it as an active confirmed opening.
- If no jobs qualify, report zero qualifying jobs rather than relaxing the filters.

## Match scoring (estimate, not actual ATS)
Calculate a transparent estimated profile-match score out of 100:
- 35 points: core technical match (Azure, Terraform, Linux, Ansible, CI/CD, cloud networking, monitoring, scripting).
- 20 points: duties match (provisioning, operations, incident response, hardening, automation).
- 15 points: experience fit (3–6 years; prioritize 4–5).
- 10 points: location and India work eligibility.
- 10 points: relevant production scale/impact (100+ servers, 99.9% uptime, $2.5M platform, compliance automation).
- 5 points: role and employer fit (direct employer, relevant product/startup/cloud team).
- 5 points: evidence quality (official job page, clear date, clear location/eligibility).
Penalize missing mandatory skills or hard requirements that the resume does not substantiate. Do not claim this is the employer's real ATS score. Include 2–4 short reasons supporting the score.

## Recommendations
- **APPLY:** strong technical fit, eligible location, credible posting date within 24 hours, active vacancy, and direct application route.
- **REVIEW:** promising role but a material detail is uncertain (e.g., date, India remote eligibility, unclear employer, or one important skill gap). Clearly state the uncertainty.
- **SKIP:** hard experience mismatch, ineligible geography, poor technical fit, closed vacancy, or agency listing without an identified employer.
Do not use “APPLY” for a date-unverified or geographically unverified job.

## Deduplication and history
- Deduplicate by employer + normalized job title + location/job ID.
- If the same role appears on multiple sites, show it once; list discovery sources and prioritize the official application URL.
- Maintain `data/jobs_history.json` with job ID/URL, company, title, location, first discovered date, original posting date, last verified date, source URLs, status, score, recommendation, and application status.
- Do not re-report an old job as new just because it was reposted or re-indexed. If its original posting date is unclear, mark it for review.
- Never submit applications, contact recruiters, or modify the candidate's public profiles without explicit user authorization.

## Daily schedule and outputs
- Intended schedule: **08:30 Asia/Kolkata every day**.
- Do not claim a schedule is active until the local scheduler or automation has actually been configured and tested. If scheduling is not configured, state that clearly.
- Each run should create:
  - `reports/latest.html` — readable report.
  - `reports/latest.csv` — sortable spreadsheet-compatible table.
  - `reports/latest.json` — structured results.
  - A dated archive under `reports/archive/`.
  - Updated `data/jobs_history.json` and a run log.
- Include a run timestamp and a short source-coverage summary, noting inaccessible sources.
- If zero roles qualify, show the filters and sources checked; do not fill the report with stale jobs.

## Report layout
1. **Bengaluru — Confirmed matches** (highest priority).
2. **Other India locations — Confirmed matches**.
3. **Worldwide remote — Confirmed India-eligible matches**.
4. **Wellfound startup leads — date/employer verification pending**, if any.
5. **LinkedIn leads — official verification pending**, if any.
6. **Date or location unverified — review manually**, if any.
7. **Excluded examples / reasons** (brief summary, no large dump).

For every listing show:
- Title, company, location, work arrangement.
- Original posting date and last verified timestamp.
- Required years and candidate experience comparison.
- Key matching and missing skills.
- Estimated match score with reasons.
- Recommendation and concise rationale.
- Discovery source(s), verification status, and direct application URL.

## Final quality checklist
Before publishing:
- Is the vacancy still open?
- Is the original posting date within 24 hours, or explicitly separated as unverified?
- Is the actual employer identified?
- Does the experience requirement fit?
- Is Bengaluru/India/worldwide-remote eligibility clear?
- Is worldwide remote explicitly open to India-based applicants?
- Is the application URL direct and valid?
- Is the role a genuine technical match for this resume?
- Are repeated listings deduplicated?
- Are unsupported claims and invented details absent?
