"""Add a Sauce Labs section to the Azure DevOps run Summary page: every test, its result and job link.

Reads the sauce_job_url properties the driver fixture writes into the JUnit report.
Usage: python ci/sauce_summary.py [reports/junit.xml]
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

junit = Path(sys.argv[1] if len(sys.argv) > 1 else "reports/junit.xml")
if not junit.exists():
    print(f"##vso[task.logissue type=warning]{junit} not found - no Sauce Labs summary")
    sys.exit(0)

rows, failed = [], 0
for case in ET.parse(junit).iter("testcase"):
    url = {p.get("name"): p.get("value") for p in case.iter("property")}.get("sauce_job_url")
    if case.find("failure") is not None or case.find("error") is not None:
        status, failed = "❌ Failed", failed + 1
    elif case.find("skipped") is not None:
        status = "⏭ Skipped"
    else:
        status = "✅ Passed"
    link = f"[Open in Sauce Labs]({url})" if url else "-"
    rows.append(f"| {case.get('name')} | {status} | {link} |")
    print(f"{status}  {case.get('name')}  {url or '-'}")  # also visible in the step log

out = junit.with_name("sauce-summary.md")
out.write_text("\n".join([f"**{len(rows)} tests, {failed} failed**", "",
                          "| Test | Result | Sauce Labs job |", "|---|---|---|", *rows]) + "\n",
               encoding="utf-8")
print(f"##vso[task.addattachment type=Distributedtask.Core.Summary;name=Sauce Labs]{out.resolve()}")
