#!/usr/bin/env python3
"""Create LineSight's measured technical report from experiment evidence.

Owner: Kumar Waibhav Akshat <kwa.waibhav@gmail.com>.
Run after evaluation and verification; no training or metric selection occurs.
"""
from __future__ import annotations

import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image as ReportImage, PageBreak,
)

ROOT = Path(__file__).resolve().parents[1]
INK = colors.HexColor("#10283d")
TEAL = colors.HexColor("#008c8c")
MUTED = colors.HexColor("#536779")
LIGHT = colors.HexColor("#eef5f7")
ORANGE = colors.HexColor("#ca663c")


def main() -> None:
    metrics = json.loads((ROOT / "reports/metrics.json").read_text())
    frozen = json.loads((ROOT / "reports/frozen_model.json").read_text())
    selection = json.loads((ROOT / "reports/selection.json").read_text())
    test_file = ROOT / "reports/verification.json"
    verification = json.loads(test_file.read_text()) if test_file.is_file() else {}
    runtime_file = ROOT / "reports/runtime_verification.json"
    runtime = json.loads(runtime_file.read_text()) if runtime_file.is_file() else {}
    font_root = Path("/usr/share/fonts/truetype/dejavu")
    if (font_root / "DejaVuSans.ttf").is_file():
        pdfmetrics.registerFont(TTFont("LS", str(font_root / "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("LS-Bold", str(font_root / "DejaVuSans-Bold.ttf")))
        pdfmetrics.registerFontFamily("LS", normal="LS", bold="LS-Bold", italic="LS", boldItalic="LS-Bold")
        regular, bold = "LS", "LS-Bold"
    else:
        regular, bold = "Helvetica", "Helvetica-Bold"
    styles = getSampleStyleSheet()
    for name in ["BodyText", "Normal"]:
        styles[name].fontName = regular
        styles[name].fontSize = 9
        styles[name].leading = 14
        styles[name].textColor = INK
    styles.add(ParagraphStyle("TitleLS", fontName=bold, fontSize=35, leading=42, textColor=INK, spaceAfter=16))
    styles.add(ParagraphStyle("H1LS", fontName=bold, fontSize=19, leading=25, textColor=INK, spaceAfter=13))
    styles.add(ParagraphStyle("H2LS", fontName=bold, fontSize=11, leading=16, textColor=TEAL, spaceBefore=13, spaceAfter=6))
    styles.add(ParagraphStyle("SmallLS", fontName=regular, fontSize=7.7, leading=11.7, textColor=MUTED))
    styles.add(ParagraphStyle("KickerLS", fontName=bold, fontSize=8, leading=12, textColor=TEAL, spaceAfter=8))
    styles.add(ParagraphStyle("CellLS", fontName=regular, fontSize=8, leading=11, textColor=INK, alignment=TA_LEFT))
    styles.add(ParagraphStyle("WhiteLS", fontName=bold, fontSize=8, leading=11, textColor=colors.white))
    W = 7.1 * inch
    story = []

    def p(text: str, style="BodyText") -> Paragraph:
        return Paragraph(text, styles[style])

    def body(text: str) -> None:
        story.extend([p(text), Spacer(1, 7)])

    def heading(number: int, title: str) -> None:
        story.extend([p(f"TECHNICAL REPORT / {number:02}", "KickerLS"), p(title, "H1LS")])

    def table(rows, widths=None):
        data = [[p(str(cell), "WhiteLS" if i == 0 else "CellLS") for cell in row] for i, row in enumerate(rows)]
        t = Table(data, colWidths=widths, hAlign="LEFT", repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), INK), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("LINEBELOW", (0, -1), (-1, -1), .5, colors.HexColor("#cddde3")),
        ]))
        story.extend([t, Spacer(1, 11)])

    def figure(name: str, width=W, max_height=None):
        from PIL import Image
        path = ROOT / "reports/figures" / name
        with Image.open(path) as im:
            iw, ih = im.size
        height = width * ih / iw
        if max_height and height > max_height:
            width *= max_height / height
            height = max_height
        story.extend([ReportImage(str(path), width=width, height=height), Spacer(1, 7)])

    # Page 1: concrete outcome and scope.
    story.extend([Spacer(1, 15), p("COMPUTER VISION / INDUSTRIAL QUALITY", "KickerLS"),
                  p("LineSight", "TitleLS"), p("Visual anomaly detection for production lines", "H1LS")])
    body("A complete CPU-first inspection project built around a normal-only Isolation Forest, "
         "real industrial bottle images, a local inspection application, and auditable experiment evidence.")
    story.extend([Spacer(1, 12), p("Kumar Waibhav Akshat", "H2LS"),
                  p("kwa.waibhav@gmail.com | 22 October 2026", "SmallLS"), Spacer(1, 20)])
    table([["HELD-OUT AUROC", "DEFECT RECALL", "PRECISION"],
           [f"{metrics['auroc']:.4f}", f"{metrics['recall']:.2%}", f"{metrics['precision']:.2%}"]], [W / 3] * 3)
    story.append(p("The real-world problem", "H2LS"))
    body("Bottle production needs to identify breakage and contamination even when labeled defect "
         "examples are scarce. A fixed camera can collect normal parts; LineSight learns their visual "
         "pattern and flags unusual images for an operator to review. This benchmark models that "
         "inspection task; it does not represent an installed factory system.")
    story.append(p("What is delivered", "H2LS"))
    body("Verified dataset preparation; four development candidates; frozen calibrated model; "
         "held-out predictions and uncertainty; five result figures; upload/replay/camera dashboard; "
         "FastAPI and SQLite; tests, dependency audit, CI, container recipe, executed notebook, "
         "model/dataset cards, and GitHub-ready local source.")
    story.append(p("How to read the results", "H2LS"))
    body("The selected model detected <b>53 of 63 defects</b>, missed <b>10</b>, and flagged "
         "<b>2 of 20 normal bottles</b>. It requires a controlled view and lighting. Camera/lighting "
         "changes produced substantial false alarms in sensitivity probes. No claim of perfection, "
         "general-purpose vision, or hard real-time factory performance is supported.")
    story.append(PageBreak())

    # Page 2: dataset and method.
    heading(2, "Data, architecture and model logic")
    body("<b>Data:</b> MVTec AD bottle, 292 original 900 x 900 images and 63 defect masks. "
         "Acquisition uses a pinned public mirror. Its archive digest, structural counts, per-image "
         "digests and duplicate checks were verified; official-download byte equivalence was not "
         "independently established. The original official train/test roles are retained.")
    table([["Partition", "Images", "Role"], ["Fit", "125 normal", "Learn median/MAD reference and fit forest"],
           ["Tune", "42 normal + 126 proxy variants", "Compare candidates using synthetic defects only"],
           ["Calibration", "42 normal", "Set independent score threshold"],
           ["Official test", "20 normal + 63 defective", "Evaluate once after design/threshold freeze"]], [1.0*inch, 1.8*inch, W-2.8*inch])
    story.append(p("Offline and online architecture", "H2LS"))
    table([["Stage", "Flow"],
           ["Offline", "Pinned images &gt; audited manifest &gt; fit-only reference &gt; candidate forests &gt; tune proxy selection &gt; independent calibration &gt; frozen artifact &gt; held-out evaluation"],
           ["Online", "Upload / recorded replay / sampled camera &gt; bounded image validation &gt; fixed descriptors &gt; Isolation Forest &gt; score / threshold / coarse evidence &gt; operator view and SQLite event"]], [1.0*inch, W-1.0*inch])
    story.append(p("Feature construction and detector", "H2LS"))
    body("Inputs are normalized to RGB and resized to 192 x 192. Robust per-pixel median and "
         "MAD statistics are learned from fit normals. Color and gradient residuals, brightness and "
         "edge statistics form 16 descriptors over each of 144 non-overlapping 16 x 16 patches. "
         "The selected forest contains 192 trees with 512 samples per tree. Each image receives "
         "the maximum negative <font name='Courier'>score_samples</font> patch score.")
    body("Isolation trees randomly split features. Unusual feature vectors tend to isolate with "
         "shorter paths. Larger exposed scores mean more anomalous; they are not probabilities. "
         "The 12 x 12 evidence grid is a coarse score map, not a validated segmentation output.")
    story.append(PageBreak())

    # Page 3: credible development and calibration.
    heading(3, "Development, calibration and reproducibility")
    body("Candidate development used tune normals and deterministic scratches, blobs and inverted "
         "patches derived only from those tune images. No real test defect or test score selected "
         "the model or threshold. Proxy performance is a development signal, not real-defect evidence.")
    table([["Candidate", "Proxy AUROC", "Selected"]] +
          [[r["candidate"], f"{r['proxy_auroc']:.4f}", "Yes" if r["candidate"] == frozen["selected_candidate"] else ""]
           for r in selection["candidates"]], [W*.5, W*.25, W*.25])
    cal = frozen["calibration"]
    story.append(p("Independent nominal threshold", "H2LS"))
    body(f"For n = {cal['n']} calibration normals and alpha = {cal['alpha']}, the upper rank is "
         f"ceil((n + 1) x (1 - alpha)) = {cal['rank_one_indexed']}. The frozen threshold is "
         f"<b>{cal['threshold']:.8f}</b>, with a strict score &gt; threshold decision. The finite-sample "
         f"nominal error bound is {cal['nominal_error_bound_under_exchangeability']:.2%} under exchangeability. "
         "This is a marginal nominal coverage statement, not a promise about this small test set or "
         "a shifted camera domain.")
    story.append(p("Audit trail", "H2LS"))
    body(f"Model identifier: <b>{frozen['model_version']}</b>. The frozen artifact and dataset manifest "
         "digests are checked before evaluation. Selection history, proxy descriptions, seed rules, "
         "normal calibration scores and all 83 test predictions are stored in CSV/JSON files. "
         "The random seed is 42; uncertainty resampling uses seed 2026.")
    body("Original fit environment: Python " + frozen["versions"]["python"] + ", scikit-learn " + frozen["versions"]["scikit_learn"] +
         ", Pillow " + frozen["versions"]["pillow"] + ". Deployment runtime pins Pillow 13.0.0 after "
         "a dependency-security correction. The frozen artifact is retained; a separate verification "
         "checks all original test scores against the updated image library without changing selection.")
    if runtime:
        body("Runtime verification: " + escape(str(runtime.get("summary", "See reports/runtime_verification.json for measured equivalence."))))
    story.append(p("Licensing", "H2LS"))
    body("Original code is MIT licensed. The MVTec dataset and supplied dataset-derived visuals "
         "and pretrained material are provided under CC BY-NC-SA 4.0 for noncommercial work. "
         "Commercial deployment needs separately licensed data and retraining.")
    story.append(PageBreak())

    # Page 4: evidence, not only headline.
    heading(4, "Held-out performance and uncertainty")
    ci = metrics["uncertainty"]["intervals"]
    table([["Metric", "Observed", "95% stratified bootstrap interval"]] +
          [[label, f"{metrics[key]:.4f}", f"{ci[key][0]:.4f} - {ci[key][1]:.4f}"]
           for key, label in [("auroc", "AUROC"), ("average_precision", "Average precision"),
                              ("precision", "Precision"), ("recall", "Defect recall"), ("f1", "F1")]],
          [1.6*inch, 1.1*inch, W-2.7*inch])
    figure("roc_pr.png")
    body("Intervals use 2,000 class-stratified percentile bootstrap samples. They condition on "
         "this small, defect-heavy benchmark mix; they do not estimate factory generalization "
         "or production precision at a low defect prevalence.")
    table([["Real defect", "Detected / total", "Recall"]] +
          [[name.replace("_", " "), f"{v['detected']} / {v['n']}", f"{v['recall']:.2%}"]
           for name, v in metrics["per_defect"].items()], [W*.5, W*.25, W*.25])
    base = metrics["reference_baseline"]
    body(f"A simple fit-reference residual baseline achieved AUROC {base['auroc']:.4f}, "
         f"recall {base['recall']:.2%}, and F1 {base['f1']:.4f}. Isolation Forest provides a modest "
         "observed improvement on this split; no significance or state-of-the-art claim is made.")
    story.append(PageBreak())

    # Page 5: failure and evidence charts.
    heading(5, "Decisions, misses and sensitivity")
    figure("scores_confusion.png")
    figure("development_robustness.png")
    body("The fixed threshold missed 10 defective images, especially contamination (14 of 21 "
         "detected), and produced two false alarms. Reducing brightness to 80% or translating "
         "the resized view by eight pixels flagged every normal test image. These are controlled "
         "post-freeze sensitivity probes, not additional model-selection runs. Correct camera "
         "alignment and stable illumination are operational prerequisites.")
    table([["Condition", "Defect recall", "Normal false alarms"]] +
          [[name.replace("_", " "), f"{v['recall']:.2%}", f"{v['false_positive_rate']:.2%}"]
           for name, v in metrics["stress_tests"].items()], [W*.5, W*.25, W*.25])
    story.append(PageBreak())

    # Page 6: visually readable inspection panel.
    heading(6, "Visual inspection evidence")
    body("Reproducible representatives are shown with their decision score, coarse patch "
         "evidence and the dataset annotation. When a decision error exists it is promoted into "
         "the example selection. The annotation is not consumed by training or the deployed detector.")
    figure("inspection_examples.png", max_height=8.0*inch)
    story.append(p("Dataset-derived images: MVTec AD, CC BY-NC-SA 4.0. No pixel segmentation metric is claimed.", "SmallLS"))
    story.append(PageBreak())

    # Page 7: functioning application and verified constraints.
    heading(7, "Application, tests and deployment path")
    body("The local dashboard sends actual images to the same frozen detector used in evaluation. "
         "It supports uploads, clearly labeled recorded replay, sampled browser-camera frames, "
         "a coarse evidence overlay and a bounded local decision history. SQLite retains at most "
         "1,000 metadata records. Uploaded images are not retained.")
    table([["Verification area", "Evidence / behavior"],
           ["Model and data", "Partition isolation, all source digests, calibration rank and nominal error math, score orientation, deterministic persistence, stored prediction reconciliation"],
           ["API and security", "Missing-model readiness, image bytes/pixels/formats, bounded inspection requests, invalid inputs, history retention, sample path confinement, API reference, real detector integration"],
           ["Application", "Managed browser review of dashboard, dataset inspection and history; physical camera validation unavailable" if verification.get("browser", {}).get("verified") else "API integration verified; browser review not completed in this environment. Physical camera validation unavailable"],
           ["Dependencies", "Pinned runtime and recorded advisory audit; image library upgraded with frozen-score equivalence check"],
           ["Deployment", "Native local service verified. Nonroot Docker/Compose recipe supplied; container build was not run because Docker is unavailable"],
           ["Repository", "Local main branch, owner-only Git identity, CI recipe, no remote, no push or external publication"]], [1.3*inch, W-1.3*inch])
    if verification:
        body("Recorded validation: " + escape(str(verification.get("summary", "See reports/verification.json and reports/pytest.xml for exact results."))))
    latency = metrics["latency_ms"]
    story.append(p("Measured runtime", "H2LS"))
    body(f"Original benchmark CPU inference p50 was {latency['p50']:.2f} ms and p95 "
         f"{latency['p95']:.2f} ms, batch size one, one forest thread, across 83 images after "
         "two warmups. It includes resizing, features and forest scoring; excludes image decode, "
         "HTTP, capture, queueing and SQLite. Shared-host load affects these timings. Browser "
         "camera sampling targets about 1.2 seconds between completed requests. This is a soft "
         "inspection demonstration, not a validated line-speed or hard real-time guarantee.")
    story.append(PageBreak())

    # Page 8: practical handoff.
    heading(8, "Reproduction, handoff and next validation")
    table([["Task", "Command / location"],
           ["Install", "python -m pip install -r requirements.lock<br/>python -m pip install -e '.[dev]'"],
           ["Acquire / validate data", "python scripts/download_data.py<br/>python scripts/download_data.py --verify-only"],
           ["Train / freeze", "python scripts/train.py"],
           ["Evaluate", "python scripts/evaluate.py"],
           ["Tests", "python -m pytest -q"],
           ["Use dashboard", "python scripts/serve.py<br/>http://127.0.0.1:8000"],
           ["Notebook", "notebooks/01_linesight_walkthrough.ipynb"],
           ["Read model / data details", "docs/model-card.md; docs/dataset-card.md"],
           ["Inspect exact evidence", "reports/metrics.json; test_predictions.csv;<br/>frozen_model.json; runtime_verification.json; pytest.xml"],
           ["Build delivery archives", "python scripts/package_release.py"]], [1.6*inch, W-1.6*inch])
    story.append(p("Before a real production pilot", "H2LS"))
    body("Collect licensed normal images from the actual camera, product, alignment and lighting. "
         "Separate batches or acquisition periods when splitting data. Gather independent defect "
         "examples and enough normal images to measure operational false alarms. Define acceptable "
         "miss/false-alarm costs, review queues, drift monitoring and operator escalation. Add "
         "authentication, TLS, resource/time limits and observability before network exposure. "
         "Physical rejector integration requires separate hardware timing and safety validation.")
    story.append(p("Sources and attribution", "H2LS"))
    body("Bergmann, P., Fauser, M., Sattlegger, D., and Steger, C. (2019). MVTec AD - A "
         "Comprehensive Real-World Dataset for Unsupervised Anomaly Detection. CVPR. "
         "Official dataset: www.mvtec.com/research-teaching/datasets/mvtec-ad.")
    body("Isolation Forest implementation: scikit-learn, "
         "scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html. "
         "Pinned acquisition, licenses and primary reference links are recorded in the repository.")
    body("<b>Project owner:</b> Kumar Waibhav Akshat | kwa.waibhav@gmail.com. "
         "The supplied repository is prepared locally for review and future GitHub publication; "
         "nothing has been pushed or published externally.")

    output = ROOT / "output/pdf/LineSight_Technical_Report.pdf"
    output.parent.mkdir(parents=True, exist_ok=True)

    def page_canvas(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(TEAL)
        canvas.rect(0, doc.pagesize[1]-8, doc.pagesize[0], 8, fill=1, stroke=0)
        canvas.setStrokeColor(colors.HexColor("#d7e4e8"))
        canvas.line(.6*inch, .48*inch, doc.pagesize[0]-.6*inch, .48*inch)
        canvas.setFillColor(MUTED)
        canvas.setFont(regular, 7)
        canvas.drawString(.6*inch, .32*inch, "LINESIGHT / Kumar Waibhav Akshat / Technical report")
        canvas.drawRightString(doc.pagesize[0]-.6*inch, .32*inch, f"{doc.page:02d}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(output), pagesize=(8.3*inch,11.7*inch),
                            rightMargin=.6*inch,leftMargin=.6*inch,topMargin=.65*inch,bottomMargin=.7*inch,
                            title="LineSight - Technical Report", author="Kumar Waibhav Akshat")
    doc.build(story, onFirstPage=page_canvas, onLaterPages=page_canvas)
    print(output)


if __name__ == "__main__":
    main()
