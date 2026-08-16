"""Ask the model to prepare the packet, with the rules and the answer list.

The help here is deliberate and disclosed: the model is handed the published
requirements it must satisfy and a fixed vocabulary of blocking issues to choose
from. If it still misses a defect with the answer list in view, no amount of
product polish will fix that. If it catches everything, the packet leg is
form-filling and the product has to live somewhere else.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .scenarios import ISSUE_CODES, Scenario

REQUIREMENTS = """Published requirements for a dbGaP controlled-access request:

1. The Principal Investigator and the institution's Signing Official co-sign the
   request. Both use eRA Commons accounts. A department chair or a postdoc
   cannot substitute for the registered Signing Official.
2. The Research Use Statement must be consistent with the data use limitation of
   every dataset requested. A request whose stated use does not match the
   limitation is rejected; the remedy is to drop the dataset or change the use.
3. Collaborating investigators listed on the request are those at the same
   institution. Collaborators at other institutions must submit separate
   requests for co-submission with their own Signing Officials.
4. Some datasets require local IRB approval, as stated on the study page.
5. Under the Data Use Certification, use is limited to the project described in
   the request, the data may not be distributed beyond those permitted to handle
   it, and recipients must not attempt to identify or contact participants.
6. Access lasts one year. The PI must submit a renewal or a close-out request
   before the expiration date; failure can terminate access and suspend the PI
   and all associated personnel."""

SCHEMA = {
    "type": "object",
    "properties": {
        "blocking_issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "enum": list(ISSUE_CODES)},
                    "explanation": {"type": "string"},
                },
                "required": ["code", "explanation"],
            },
        },
        "research_use_statement": {"type": "string"},
        "principal_investigator": {"type": "string"},
        "signing_official": {"type": "string"},
        "personnel": {"type": "array", "items": {"type": "string"}},
        "era_commons_id": {"type": "string"},
        "irb_approval_number": {"type": "string"},
        "dataset_accession": {"type": "string"},
        "unknowns": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["blocking_issues", "research_use_statement",
                 "principal_investigator", "signing_official", "personnel",
                 "unknowns"],
}

PROMPT = """You prepare dbGaP controlled-access data requests for researchers.

{requirements}

A researcher writes:

{request}

Dataset requested: {dataset}
Its data use limitation: {dul}

Prepare the request packet. List every blocking issue that would cause this
request to be rejected or returned, choosing codes from the fixed list. If there
are none, return a single issue with code NONE.

Do not invent identifiers. If an eRA Commons id, IRB approval number or dataset
accession was not given to you, leave that field empty and name it under
unknowns."""


@dataclass(frozen=True, slots=True)
class Packet:
    scenario: str
    run: int
    answer: dict
    prompt_tokens: int
    output_tokens: int
    seconds: float
    error: str = ""

    def as_dict(self) -> dict:
        return {
            "scenario": self.scenario, "run": self.run, "answer": self.answer,
            "prompt_tokens": self.prompt_tokens,
            "output_tokens": self.output_tokens,
            "seconds": round(self.seconds, 2), "error": self.error,
        }


def prepare(scenario: Scenario, run: int, model) -> Packet:
    call = model.ask(
        PROMPT.format(requirements=REQUIREMENTS, request=scenario.request,
                      dataset=scenario.dataset, dul=scenario.dul),
        SCHEMA,
    )
    try:
        answer = json.loads(call.text)
    except (json.JSONDecodeError, TypeError):
        answer = {}
    return Packet(scenario.id, run, answer if isinstance(answer, dict) else {},
                  call.prompt_tokens, call.output_tokens, call.seconds,
                  call.error)
