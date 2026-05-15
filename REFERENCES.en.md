# Research References

The default zoning and parameter values in this project are engineering defaults derived from public literature, not clinical prescriptions. The current default profile prioritizes healthy adults, especially healthy young Asian male baseline data, then combines that with insole structure research.

## 1. Plantar pressure redistribution in asymptomatic healthy men

- [Pressure Properties of Three Different Types of Prefabricated Insoles Related to Plantar Pressure in Asymptomatic Men](https://pmc.ncbi.nlm.nih.gov/articles/PMC9715923/)

Short note:

- This study compares how arch support, metatarsal padding, and a lateral heel wedge redistribute pressure in asymptomatic healthy men.
- It supports keeping `innerHeel / outerHeel`, `innerArch / outerArch`, and the three-part forefoot layout while tuning the default profile toward neutral support instead of pathology-oriented offloading.

## 2. Baseline plantar pressure in healthy young Chinese adults

- [Foot Pressure Analysis in Normal Young Chinese Adults](https://www.airitilibrary.com/Article/Detail/10137688-199704-22-2-81-90-a)

Short note:

- This study provides baseline plantar pressure data for healthy young Chinese adults during standing and gait.
- The abstract reports peak walking pressure around the 2nd metatarsal head, with the gait line starting at the lateral heel and progressing toward the central forefoot.
- This supports giving `centralForefoot` more importance in the default profile and preserving normal landing compliance in `outerHeel`.

## 3. Total contact and arch support

- [Advancements in diabetic foot insoles: a comprehensive review of design, manufacturing, and performance evaluation](https://www.frontiersin.org/journals/bioengineering-and-biotechnology/articles/10.3389/fbioe.2024.1394758/full)

Short note:

- The review highlights the importance of total-contact customization, soft/stiff material combinations, and porous structures for plantar pressure redistribution.
- This supports treating `innerArch` as the main support region while keeping a contact skin and porous internal lattice.

## 4. How to use these sources

- These sources are best used to choose a reasonable default zoning strategy and tuning direction.
- If plantar pressure maps, gait data, or wear-test feedback become available, those individual data sources should override the default settings.
