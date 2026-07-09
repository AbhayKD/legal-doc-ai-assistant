# Scaling an ML-Powered Vehicle Salvage Assessment System from POC to Production

## The Problem and Context

At Tractable, our core product uses computer vision to identify vehicle damage from images — detecting dents, scratches, and structural damage for insurance claims. The product team identified a new market opportunity: the salvage industry. When a vehicle is declared a total loss, salvage companies need to determine which parts can be recovered and resold in the second-hand market. This is traditionally done by manual inspection — slow, inconsistent, and expensive. This represented Tractable's first expansion beyond insurance into adjacent markets — a significant strategic bet for the company.

The challenge was to adapt our existing damage detection pipeline to solve a fundamentally different question: not "what's damaged?" but "what's still reusable?" — and deliver it in a format the salvage industry actually understands (Hollander interchange codes, not our internal part taxonomy).

## Complexity and Constraints

Several factors made this technically challenging:

**Domain translation.** Our ML models identified damage using Tractable's internal part classification. Salvage customers only understand Hollander codes — an industry-standard interchange system for vehicle parts. Bridging these required VIN decoding (to determine make, model, year), then mapping our detected parts to the correct Hollander codes for that specific vehicle. Each customer provided different mapping data with different formats and coverage.

**Reusing infrastructure without breaking it.** The capture and condition models (which verify image quality, identify panels, and assess damage extent) were shared with the core insurance product. Any changes for salvage had to be non-disruptive to existing customers. We considered building a separate ML pipeline for salvage, but reusing the existing models meant faster time-to-market and no model maintenance duplication. The trade-off was tighter coupling — salvage SLA requirements now constrained how we could deploy shared models.

**Stringent SLAs.** One customer required 500 requests processed within a one-hour window, with no more than 4 failures per 1,000 requests. We had to balance between scaling GPU capacity (expensive) and optimising the pipeline (complex), since the models served multiple products simultaneously.

**Third-party dependencies.** VIN decoding relied on external services with rate limits and inconsistent data quality, requiring fallback strategies across multiple paid decoding providers.

## My Approach

I led this as tech lead, starting with one research engineer and delivering a POC within two months. As the product scaled, the team grew to include three more engineers and two researchers.

**Architecture:** We built on the existing Tractable ML pipeline rather than creating a parallel system. The salvage workflow orchestrated the same capture/condition models but added a post-processing layer: a Vehicle Interchange Service that translated our internal part assessments into customer-specific Hollander codes. This kept the core models stable while allowing salvage-specific logic to evolve independently.

**ML pipeline:** We trained regression models on customer-provided data mapping make/model/year combinations to their Hollander code catalogues. The VIN to make/model/year to Hollander code chain gave us the translation layer between our detection output and what salvage customers needed.

**Performance optimisation:** To meet SLAs without simply throwing GPU capacity at the problem, we optimised at multiple levels: selecting the right floating-point precision (FP16 vs FP32) per model based on accuracy-latency trade-offs, implementing dynamic batching to maximise GPU utilisation, bin-packing models efficiently across available hardware, and running certain models in a slimmer serving mode for faster inference. We also implemented model ensembling where it improved accuracy without proportionally increasing latency. These optimisations met the 500 requests/hour requirement without proportionally scaling infrastructure costs.

## Impact

- Scaled from 100-200 requests/day (single POC customer) to 5,000 requests/day across four use cases in the US and EU, with expansion underway to Japan.
- Met all SLA requirements: <4 failures per 1,000 requests, 500 requests/hour processing capacity.
- Opened an entirely new market segment for Tractable — salvage was a net-new revenue stream built on existing ML infrastructure.
- The team grew from 2 to 7, validating the investment in this product line.

## Reflection

Two things I would do differently:

**1. Invest in a proper VIN decoding service from day one.** Under delivery pressure, we integrated VIN decoding as a library within our workflow. Another team later needed the same capability and built their own. A well-architected, centrally maintained VIN decoding service — properly rate-limited, multi-provider with fallback, and battle-tested — would have served both teams and avoided duplicate effort.

**2. Automate the model training pipeline for customer-specific mappings.** Each new customer brought their own Hollander code mapping data in different formats. The pipeline to ingest this data, train the regression model, and validate output quality required significant manual work. Automating this end-to-end would have dramatically reduced onboarding time for new customers and improved data quality consistency.
