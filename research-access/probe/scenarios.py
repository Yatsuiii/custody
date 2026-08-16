"""Eight dbGaP access requests, seven with one planted defect each.

Every defect is wrong according to a specific published NIH requirement, and
each scenario records which one, so a disagreement about grading is a
disagreement about NIH's text rather than about my judgement. The eighth is
clean: a system that invents problems where there are none is as useless here as
one that misses them, and without a control that failure is invisible.

Nothing in this file is submitted anywhere. It is a paper exercise against
published rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The fixed vocabulary the model chooses from. Giving it the enum is deliberate
# help: if it still misses a defect with the answer list in hand, the gap is
# real, and if it does well, the advantage is disclosed rather than hidden.
ISSUE_CODES = (
    "DUL_MISMATCH",
    "EXTERNAL_COLLABORATOR_NEEDS_OWN_REQUEST",
    "SIGNING_OFFICIAL_MISSING_OR_WRONG",
    "IRB_APPROVAL_REQUIRED",
    "REDISTRIBUTION_BEYOND_PERMITTED",
    "RENEWAL_OR_CLOSEOUT_REQUIRED",
    "REIDENTIFICATION_OR_RECONTACT",
    "NONE",
)


@dataclass(frozen=True, slots=True)
class Scenario:
    id: str
    request: str
    dataset: str
    dul: str
    expected: str
    authority: str
    _: dict = field(default_factory=dict, repr=False)


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        "S1-dul-mismatch",
        "I am Dr Priya Raman, a tenured associate professor at Northfield "
        "University with an eRA Commons account. I want to use this dataset to "
        "study common variants associated with type 2 diabetes progression. "
        "The analysis will run on our institutional cluster. My two graduate "
        "students, both at Northfield, will work on it. Our Signing Official "
        "is Margaret Chen in the Office of Sponsored Research.",
        "phs-CARDIO-A: genotypes and phenotypes from a cardiovascular cohort",
        "Use limited to cardiovascular disease research only.",
        "DUL_MISMATCH",
        "NBK570242: requests are rejected when the stated data use does not "
        "match the data use limitation of the selected datasets.",
    ),
    Scenario(
        "S2-external-collaborator",
        "I am Dr Alan Whitfield, professor at Northfield University, eRA "
        "Commons account active. I want this dataset to study general "
        "population variation in lipid metabolism. My collaborator Dr Sofia "
        "Marchetti at Grantham Institute, a different institution, will "
        "download and analyse the data alongside my lab. Our Signing Official "
        "is Margaret Chen.",
        "phs-LIPID-B: general research use cohort",
        "General research use.",
        "EXTERNAL_COLLABORATOR_NEEDS_OWN_REQUEST",
        "dbGaP request procedures: collaborators at other institutions will "
        "need to submit separate requests for co-submission with their local "
        "Signing Officials.",
    ),
    Scenario(
        "S3-no-signing-official",
        "I am Dr Nadia Osei, assistant professor at Northfield University with "
        "an eRA Commons account. I want this dataset for general population "
        "genetics work. My postdoc will submit the request on my behalf and my "
        "department chair will approve it internally; we would rather not "
        "involve the central research office as it slows things down. All "
        "personnel are at Northfield.",
        "phs-POP-C: general research use cohort",
        "General research use.",
        "SIGNING_OFFICIAL_MISSING_OR_WRONG",
        "dbGaP request procedures: the PI and the Signing Official at the "
        "investigator's institution co-sign the request, both using eRA "
        "Commons accounts.",
    ),
    Scenario(
        "S4-irb-required",
        "I am Dr Tomas Lindqvist, professor at Northfield University, eRA "
        "Commons active, Signing Official Margaret Chen. I want this dataset "
        "to study inflammatory markers, which matches its stated use. This is "
        "secondary analysis of de-identified data so we do not plan to go to "
        "our IRB. All analysts are at Northfield.",
        "phs-INFLAM-D: inflammatory disease cohort. The study page states "
        "that local IRB approval is required for use of these data.",
        "Disease-specific research, inflammatory disease. Local IRB approval "
        "required.",
        "IRB_APPROVAL_REQUIRED",
        "NIH dbGaP guidance: some datasets require local IRB approval for use, "
        "as noted on the dbGaP study page, and applicants must follow it.",
    ),
    Scenario(
        "S5-redistribution",
        "I am Dr Helen Barros, professor at Northfield University, eRA Commons "
        "active, Signing Official Margaret Chen. General population genetics "
        "project, consistent with the dataset's stated use. Once I have the "
        "files I plan to put them on a shared drive so the visiting students "
        "in the neighbouring lab can use them for their coursework too.",
        "phs-POP-E: general research use cohort",
        "General research use.",
        "REDISTRIBUTION_BEYOND_PERMITTED",
        "Data Use Certification: use is limited to the project described in "
        "the request and the data may not be distributed beyond those "
        "permitted to handle it.",
    ),
    Scenario(
        "S6-multi-year-project",
        "I am Dr Ravi Anand, professor at Northfield University, eRA Commons "
        "active, Signing Official Margaret Chen. General population genetics, "
        "consistent with the dataset's stated use, all personnel internal. "
        "This is a four-year programme and I would like to set the access up "
        "once now so the team is not interrupted later.",
        "phs-POP-F: general research use cohort",
        "General research use.",
        "RENEWAL_OR_CLOSEOUT_REQUIRED",
        "dbGaP: access runs one year and the PI agrees to submit either a "
        "project renewal or a close-out request before the expiration date; "
        "failure can terminate access and suspend the PI and all personnel.",
    ),
    Scenario(
        "S7-recontact",
        "I am Dr Ingrid Sollberg, professor at Northfield University, eRA "
        "Commons active, Signing Official Margaret Chen. General population "
        "genetics, consistent with the dataset's stated use, all personnel "
        "internal. To enrich the phenotypes we will link participants to our "
        "regional clinical registry and invite the matched individuals to a "
        "follow-up visit.",
        "phs-POP-G: general research use cohort",
        "General research use.",
        "REIDENTIFICATION_OR_RECONTACT",
        "Data Use Certification: recipients must not attempt to identify or "
        "contact the study participants from whom the data were collected.",
    ),
    Scenario(
        "S8-clean-control",
        "I am Dr Marcus Feld, tenured professor at Northfield University with "
        "an active eRA Commons account. I want this dataset to study common "
        "variation in adult height, which is general population genetics. All "
        "three analysts are Northfield employees named on the request. "
        "Analysis stays on our institutional cluster. Our Signing Official is "
        "Margaret Chen, who is registered in eRA Commons and will co-sign. We "
        "expect the work to take eight months and will file a close-out "
        "before the one-year access period ends.",
        "phs-POP-H: general research use cohort",
        "General research use.",
        "NONE",
        "No requirement above is violated. A system that reports a blocking "
        "issue here is producing a false alarm.",
    ),
)


def with_defects() -> tuple[Scenario, ...]:
    return tuple(s for s in SCENARIOS if s.expected != "NONE")
