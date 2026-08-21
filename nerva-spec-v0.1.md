\# Nerva Specification v0.1



Status: RECONSTRUCTED  

Conformance Scope: Layer 0 and Layer 1  

Reference Implementation: Python  

Transport Binding: None  

Next Layer: UNDEFINED



\---



\## 1. Status of This Specification



The original source document for Nerva Specification v0.1 is no longer available.



This document is a controlled reconstruction of the normative contracts that are demonstrably implemented and tested in the current Nerva reference repository.



Normative material in this document is derived from:



1\. the current Python reference implementation;

2\. surviving conformance tests;

3\. surviving unit tests where needed to clarify implemented behavior;

4\. repository history and requirement identifiers;

5\. previously adopted explicit semantic revisions that are reflected by the current conformant implementation.



This reconstruction MUST NOT be interpreted as defining requirements beyond the surviving implementation and tests.



In particular:



\- Layer 0 is defined.

\- Layer 1 is defined.

\- Layer 2 is NOT defined.

\- No future transport, protocol, runtime, worker, tool, or agent semantics are implied by this document.



Any extension beyond this scope requires an Explicit Semantic Revision.



\---



\## 2. Conformance Language



The key words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, and MAY are to be interpreted as normative requirements.



An implementation is CONFORMANT only when:



1\. all requirements applicable to the component are implemented;

2\. all relevant conformance tests pass;

3\. static type checking passes under the project configuration;

4\. formatting and lint gates pass;

5\. CI passes on the supported Python versions.



A component MUST NOT be declared CONFORMANT solely because its source code has been written.



\---



\# 3. Layer 0 — Core Context and Canonical Errors



Layer 0 consists of:



\- ExecContext

\- NervaError



\---



\# 4. ExecContext



\## 4.1 Data Model



The canonical execution context contains:



\- version

\- request\_id

\- user\_id

\- session\_id

\- trace\_id

\- timeout\_ms

\- deadline\_unix\_ms

\- capabilities

\- metadata



The supported context version is:



```text

1.0

