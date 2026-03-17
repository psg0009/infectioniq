# InfectionIQ — FDA Regulatory Strategy

## 1. Product Classification

### Device Description
InfectionIQ is a software-only (SaMD — Software as a Medical Device) system that uses computer vision and machine learning to monitor hand hygiene compliance and predict surgical site infection (SSI) risk in operating rooms.

### Intended Use
To assist healthcare facilities in monitoring and improving hand hygiene compliance during surgical procedures by providing real-time tracking, risk assessment, and alerting.

### Classification
- **Product Code**: QMT (Medical Device Data System) / QAS (Clinical Decision Support)
- **Regulation Number**: 21 CFR 880.6310
- **Device Class**: Class II (with De Novo pathway consideration)
- **Risk Level**: Moderate risk — the system provides decision support but does not directly control treatment

### IMDRF SaMD Risk Category
Per the IMDRF framework (N12 document):
- **State of healthcare situation**: Non-serious (infection prevention monitoring)
- **Significance to healthcare decision**: Drives clinical management (alerts for non-compliance)
- **SaMD Category**: Category II (moderate risk)

---

## 2. Regulatory Pathway

### Recommended: 510(k) with De Novo Backup

**Primary pathway: 510(k)**
- Predicate device: Existing hand hygiene monitoring systems (e.g., electronic compliance monitoring)
- Substantial equivalence argument: Same intended use, similar technology (vision-based monitoring), similar risk profile

**Backup pathway: De Novo Classification**
- If no suitable predicate is found, pursue De Novo for novel AI-based surgical infection prevention software
- Request Class II classification with special controls

### Clinical Decision Support (CDS) Exemption Analysis
Under 21st Century Cures Act Section 3060(a), evaluate if InfectionIQ qualifies as non-device CDS:
1. Not intended to acquire, process, or analyze medical images — **Partially met** (uses video but not diagnostic imaging)
2. Intended for displaying, analyzing, or printing medical information — **Met**
3. Intended for use by healthcare professionals — **Met**
4. Intended for enabling independent review — **Met** (provides recommendations, clinician makes decisions)

**Conclusion**: The hand hygiene compliance monitoring function may qualify for CDS exemption. The SSI risk prediction component likely requires FDA clearance as SaMD.

---

## 3. Quality Management System (QMS)

### 21 CFR Part 820 Compliance

| Subpart | Requirement | Implementation |
|---------|-------------|----------------|
| B | Quality System Requirements | QMS manual, management responsibility, quality policy |
| C | Design Controls | Design history file (DHF), design reviews, V&V |
| D | Document Controls | Version-controlled documentation (Git-based) |
| E | Purchasing Controls | Vendor qualification for cloud services, libraries |
| F | Identification & Traceability | Software version tracking, deployment logs |
| G | Production & Process Controls | CI/CD pipeline, automated testing, build validation |
| H | Acceptance Activities | Release testing protocol, acceptance criteria |
| I | Nonconforming Product | Bug tracking, CAPA process |
| J | Corrective & Preventive Action | CAPA procedures, root cause analysis |
| K | Labeling | Electronic labeling, IFU (Instructions for Use) |
| L | Handling, Storage, Distribution | Cloud deployment procedures, backup/recovery |
| M | Records | Audit trail, electronic records (21 CFR Part 11) |
| N | Servicing | Software update procedures, customer support |
| O | Statistical Techniques | Statistical methods for validation studies |

### IEC 62304 Software Lifecycle
- **Software Safety Class**: Class B (non-serious injury possible through incorrect information)
- **Development Process**: Agile with documented design controls
- **Architecture Documentation**: System design specification maintained
- **Unit/Integration/System Testing**: Required per Class B

---

## 4. Pre-Submission Strategy

### Pre-Sub Meeting Topics
1. Regulatory pathway confirmation (510(k) vs De Novo)
2. Predicate device selection agreement
3. Clinical evidence expectations
4. AI/ML algorithm change protocol (PCCP)
5. Cybersecurity documentation requirements

### Timeline
- **Pre-Sub Request**: Submit Q-Sub at least 75 days before desired meeting
- **FDA Response**: ~75 days for written feedback or meeting

---

## 5. Clinical Evidence

### Performance Testing
1. **Hand Hygiene Detection Accuracy**
   - Sensitivity: ≥95% for hand wash/sanitize gesture detection
   - Specificity: ≥90% to minimize false alarms
   - Test across diverse populations, lighting, OR configurations

2. **Person Tracking Accuracy**
   - Identity maintenance across occlusions: ≥90%
   - Zone detection accuracy: ≥95%

3. **SSI Risk Prediction (if included in clearance)**
   - AUC-ROC: ≥0.75 for SSI risk stratification
   - Calibration: Hosmer-Lemeshow p > 0.05
   - Validation on independent dataset

### Clinical Validation Study
- **Design**: Prospective, multi-site observational study
- **Sites**: 3-5 hospitals, diverse settings
- **Duration**: 6-12 months per site
- **Primary Endpoint**: Hand hygiene compliance rate accuracy vs trained human observers
- **Secondary Endpoints**: User satisfaction, workflow impact, alert fatigue metrics
- **Sample Size**: ≥500 surgical cases across all sites

### Real-World Evidence
- Post-market surveillance plan
- Complaint handling and adverse event reporting (MDR)

---

## 6. AI/ML-Specific Requirements

### Predetermined Change Control Plan (PCCP)
Per FDA's AI/ML guidance (October 2023):

1. **SaMD Pre-Specifications (SPS)**
   - Model type: YOLO-based object detection, MediaPipe hand tracking, gradient-boosted risk model
   - Data sources: OR camera feeds, EMR data, dispenser telemetry
   - Performance targets: See Clinical Evidence section

2. **Algorithm Change Protocol (ACP)**
   - Retraining triggers: Performance degradation >5%, new OR configurations, new equipment
   - Validation requirements for each change category:
     - **Minor** (threshold tuning): Internal validation, no new 510(k)
     - **Moderate** (model architecture): Verification testing, FDA notification
     - **Major** (new intended use): New 510(k) submission

3. **Transparency**
   - Model card documenting training data demographics
   - Known limitations and failure modes
   - Bias assessment across patient/staff demographics

### Good Machine Learning Practice (GMLP)
- Multi-disciplinary team (clinical, engineering, regulatory)
- Representative training and test datasets
- Independent test datasets (not used in training)
- Reference standards defined by clinical experts
- Model interpretability measures

---

## 7. Cybersecurity

### Pre-Market Cybersecurity (FDA Guidance 2023)

| Requirement | Implementation |
|-------------|----------------|
| Threat modeling | STRIDE analysis of all system components |
| SBOM | Software Bill of Materials for all dependencies |
| Authentication | JWT with RBAC, SSO/SAML support |
| Encryption | AES-256 for PHI at rest, TLS 1.3 in transit |
| Access controls | Role-based, principle of least privilege |
| Audit logging | All access/modifications logged with timestamps |
| Patch management | Automated dependency scanning, update procedures |
| Incident response | IR plan, breach notification procedures |
| Penetration testing | Annual third-party penetration testing |

### HIPAA Security Rule Alignment
- Administrative safeguards: Security officer, workforce training, access management
- Physical safeguards: Server access controls (cloud provider), workstation security
- Technical safeguards: Encryption, audit controls, integrity controls, transmission security

---

## 8. Labeling & Instructions for Use

### Required Labeling Elements
1. Intended use / indications for use
2. Contraindications and limitations
3. Warnings and precautions
4. Installation and setup instructions
5. User manual (administrator and clinical user)
6. Technical specifications (camera requirements, network, compute)
7. Cybersecurity user guidance

### Electronic Labeling
- Accessible via web interface (Help section)
- PDF download available
- Version-matched to software release

---

## 9. Post-Market Requirements

### Medical Device Reporting (MDR)
- Reportable events: System failure leading to missed critical hygiene violation
- 30-day reporting for malfunctions, 5-day for serious events
- Internal escalation procedures

### Post-Market Surveillance
- Ongoing performance monitoring
- User feedback collection
- Annual performance reports
- Complaint trending and analysis

### Software Updates
- Categorized as requiring new 510(k) or not per FDA guidance
- Change documentation for all releases
- Regression testing for each update

---

## 10. Submission Timeline

| Phase | Activity | Duration |
|-------|----------|----------|
| 1 | QMS establishment, design controls | 3-4 months |
| 2 | Pre-Sub meeting preparation and execution | 3 months |
| 3 | V&V testing and clinical study design | 4-6 months |
| 4 | Clinical validation study | 6-12 months |
| 5 | 510(k) submission preparation | 2-3 months |
| 6 | FDA review | 3-6 months |
| **Total** | | **~18-30 months** |

---

## 11. Key Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| No suitable predicate device | Longer pathway (De Novo) | Early Pre-Sub to confirm pathway |
| Insufficient clinical evidence | FDA additional information request | Design robust study with FDA input |
| AI bias in diverse populations | Clearance delay, post-market issues | Representative training data, bias testing |
| Cybersecurity gaps | Refuse to accept submission | Third-party security audit pre-submission |
| Changing FDA AI/ML guidance | Strategy adjustment needed | Monitor FDA guidance updates, engage early |

---

## 12. References

- FDA Guidance: "Software as a Medical Device (SaMD): Clinical Evaluation" (2017)
- FDA Guidance: "Clinical Decision Support Software" (2022)
- FDA Guidance: "Marketing Submission Recommendations for a Predetermined Change Control Plan for AI/ML-Enabled Device Software Functions" (2023)
- FDA Guidance: "Cybersecurity in Medical Devices" (2023)
- IEC 62304:2006+A1:2015 — Medical device software lifecycle processes
- IMDRF SaMD: Key Definitions (N10) and Risk Categorization (N12)
- 21 CFR Part 820 — Quality System Regulation
- 21 CFR Part 11 — Electronic Records; Electronic Signatures
