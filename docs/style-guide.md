# Smartflow brand

Smartflow connects logistics evidence to production decisions. Keep the existing dashboard typography, spacing and status colors. The new brand mark pairs a teal S silhouette with mint flow paths; status meaning continues to come from labeled UI controls and evidence.

The transparent PNG is [smartflow-mark.png](../dashboard/public/brand/smartflow-mark.png), with an identical copy for the React demo's public assets. Use it with the Smartflow name in app navigation and alone for the favicon. Preserve its proportions and transparency; check contrast on light and dark backgrounds. Existing repository URLs, package namespaces and dataset IDs stay unchanged.

The two assessment views retain the existing dark cards and compact mode navigation. Shared surface and status colors live in `dashboard/resources/css/app.css` as `--assessment-*` tokens. Batch temperature leads with QA or unavailable evidence; the demo excursion budget remains secondary. Logistics scenarios lead with the stored recommended action and three modeled outcomes. Scenario labels describe a simulation, never a detected real incident. Keep audit details collapsed initially and preserve full provenance there.

The authenticated demo uses a fixed dark root from first paint through navigation. The existing `.dark` semantic tokens reuse the assessment palette for the sidebar, header, canvas, menus and focus states. Guest pages retain saved/system appearance preferences. Preserve the depth between the navy canvas, raised cards and selected navigation, with cyan accents and the existing amber QA warnings.

Generated with the built-in imagegen tool. Final prompt:

> Use case: logo-brand. Create one finished standalone square brand mark for Smartflow, an industrial logistics and batch-readiness decision-support product. No wordmark and no text. Design a bold, refined geometric symbol combining an abstract letter S with two smoothly connected flow paths, suggesting coordinated shipments arriving at a production decision. Minimal flat vector-like graphic with clean rounded edges and restrained negative space, one cohesive connected silhouette rather than many nodes. Deep saturated teal with a subtle electric mint accent; legible on both white and near-black interface backgrounds. Strong simple silhouette that remains recognizable as a 24px app icon. Centered mark fills about 85 percent of the square image with modest even margins. Truly transparent background, no backdrop, no shadow, no gradients, no 3D, no texture, no decorative frame, no mockup. Export-quality crisp logo artwork.
