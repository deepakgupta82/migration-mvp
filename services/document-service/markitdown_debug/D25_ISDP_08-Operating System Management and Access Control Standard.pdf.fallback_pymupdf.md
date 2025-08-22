# DEBUG: fallback_pymupdf Conversion of D25_ISDP_08-Operating System Management and Access Control Standard.pdf
Original file: D25_ISDP_08-Operating System Management and Access Control Standard.pdf
File size: 188427 bytes
Conversion strategy: fallback_pymupdf
Content length: 17080 characters
Content preview: # D25_ISDP_08-Operating System Management and Access Control Standard.pdf



--- Page 1 ---

 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
For Internal Use Only 
 
 
 
 
 
 
 
 
 
 
Document Type 
Standard 
Doc...
==================================================
# D25_ISDP_08-Operating System Management and Access Control Standard.pdf



--- Page 1 ---

 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
For Internal Use Only 
 
 
 
 
 
 
 
 
 
 
Document Type 
Standard 
Document Name 
Operating System Management and 
Access Control Standard 
Document ID 
ISDP/STD.08 
Data Classification 
Internal 
Document Owner 
Head of Information Security and 
Data Protection 
Effective Date 
29-NOV-2024 
Revision Number 
10 
Renewal Date 
28-NOV-2025 


--- Page 2 ---

 
Document Title 
Operating System Management and Access Control Standard 
Document ID 
ISDP/STD.08 
Effective Date 
29-NOV-2024 
 
ISC/STD.08 
Revision 10 (29-NOV-2024) 
Page 2 of 10  
 
Table of Contents 
 
 
1. Operating System Management and Access Control Standard .................................. 3 
1.1 
Brief Description of the Standard ...................................................................................... 3 
1.2 
Objective/s ........................................................................................................................... 3 
1.3 
Departments Involved / Scope ........................................................................................... 3 
1.4 
Pre-conditions / Requisites ................................................................................................ 3 
1.5 
Standards............................................................................................................................. 3 
1.6 
Policy / Procedure / Authority Matrix Interactions or Connections ................................. 7 
1.7 
Annexure / Attachments / Supporting Documents ........................................................... 7 
1.8 
Key Controls / Management Reports ................................................................................. 7 
2. Approval Sign-off ............................................................................................................ 8 
3. Revision Log .................................................................................................................. 10 
 
 
 
 
 
 
 


--- Page 3 ---

 
Document Title 
Operating System Management and Access Control Standard 
Document ID 
ISDP/STD.08 
Effective Date 
29-NOV-2024 
 
ISC/STD.08 
Revision 10 (29-NOV-2024) 
Page 3 of 10  
1. Operating System Management and Access Control Standard  
 
1.1 
Brief Description of the Standard  
 
NBQ have large pool of servers which hosts mission critical business applications. These systems 
provide service to bank’s internal and external customers. Thus, it is critical for the organization to 
ensure that, proper controls are implemented in IT operation and maintenance procedures to enhance 
the security and availability of systems with required performance levels.  
 
The operating system of a server is the most important component. The database, applications and 
end users or services are dependent on the stability, security and performance of the operating system. 
This standard would address the security requirements related to server operating system access, 
management, maintenance and installation. 
 
This Standard is owned by Information Security and Data Protection (ISDP) department. Responsibility 
for its annual review and update, including its effective implementation rests with ISDP. 
 
1.2 
Objective/s 
 
This Standard is a part of NBQ’s ISMS policy and also in line with other policies of NBQ. This standard 
helps all users of operating system to understand the security requirements in the day to day activities 
and also spells out clear guidelines related to operating system management. This standard ensures 
that the operating system related activities are conducted in a secured manner and also defines 
responsibilities and approval procedures clearly to avoid any ambiguity.  Any exception to this standard 
has to be documented and approved. 
 
1.3 
Departments Involved / Scope  
 
This standard covers all servers in NBQ production and DR Datacenters. This policy stands valid for all 
server operating system platforms used by NBQ. This policy is applicable to all staff / contractors / 
vendors with operating system access and operations carried out in these servers using this access. 
 
1.4 
Pre-conditions / Requisites 
 
• 
Inventory of operating systems with version details 
 
1.5 
Standards  
Installation and Upgrades:  
1.5.1. 
The operating system installation of production servers shall be carried out by 
competent personnel (System support personal / System Administrator). 
 
1.5.2. 
All vendor supplied default passwords must be changed before commissioning the 
system. 
 
1.5.3. 
Any operating system installation / upgrade must have approval from Head of IT  
 
1.5.4. 
All application specific tuning parameters shall be obtained prior to the installation. 
 


--- Page 4 ---

 
Document Title 
Operating System Management and Access Control Standard 
Document ID 
ISDP/STD.08 
Effective Date 
29-NOV-2024 
 
ISC/STD.08 
Revision 10 (29-NOV-2024) 
Page 4 of 10  
1.5.5. 
Installation has to be verified by a second person before handing over to database / 
application team. 
 
1.5.6. 
The server installation shall be in line with the approved baseline configuration 
parameters. Any exceptions must be approved. 
 
1.5.7. 
All Windows-based servers shall be installed with latest antivirus software. The virus 
definitions shall be updated automatically. 
 
1.5.8. 
Any operating system upgrade of production server shall be tested first with the 
application / database combination in a test environment. 
 
1.5.9. 
A full backup of the system data and configuration has to be taken before upgrade of 
operating system. 
 
1.5.10. Any upgrade / new installation shall go through the change management process. 
 
1.5.11. Only required software / software bundles need to be included in the installation 
procedure. Any unwanted software/services can be removed / blocked. 
 
1.5.12. An image backup has to be taken after the production installation is verified and 
approved. This backup needs to be protected till next change / migration. 
 
1.5.13. Whenever critical servers are deployed, sufficient onsite redundancy need to be 
ensured based on the approved requirements of the project. 
 
1.5.14. The servers shall be sized to cater to maximum load condition. 
 
1.5.15. Perform vulnerability assessments before deploying servers on the production  
environment in order to identify vulnerabilities in the server / operating system. 
 
1.5.16. ISDP shall verify and confirm the server configuration before commissioning.  
Operating system Patch Management: 
1.5.17. All system administrators should subscribe to patch digests / newsletters / vulnerability 
updates by the operating system vendor. 
 
1.5.18. System administrators are responsible for patch management. 
 
1.5.19. The patch management activities shall follow approved change management process. 
 
1.5.20. All patches should be tested before installing in production.  
 
1.5.21. All production and DR servers should be patched as per the Security Patch 
Management Standard. In case of any exceptions, should be approved by Head of IT 
and recorded. 
 
1.5.22. All critical patch notifications / vulnerability updates should be analyzed by system 
administrators and if applicable action should be taken immediately. 
 


--- Page 5 ---

 
Document Title 
Operating System Management and Access Control Standard 
Document ID 
ISDP/STD.08 
Effective Date 
29-NOV-2024 
 
ISC/STD.08 
Revision 10 (29-NOV-2024) 
Page 5 of 10  
1.5.23. Any patch test failures should be reported to Head of IT for further action.  
 
1.5.24. A vulnerability assessment process shall be carried out to identify the vulnerabilities on 
a quarterly basis. The report shall be recorded. 
 
1.5.25. The reported vulnerabilities shall be remediated as per the Vulnerability Management 
Standard of the bank according to the severity. 
 
Access Control: 
1.5.26. Operating system level access should be controlled by unique user ID password 
mechanism. 
 
1.5.27. All user accounts should have strong passwords as per the password policy of the 
bank. 
 
1.5.28. Privileged user account passwords of production, DR and any mandated critical servers 
would not be kept with the administrators; rather would be controlled and managed by 
Privileged Access Management (PAM) solution. 
 
1.5.29. System administrators shall manage the system access as per the policy guidelines 
and approval procedures. Any exceptions should be notified and recorded. 
 
1.5.30. The production system super user session of operating system would be available to 
approved system administrators on demand. The access and actions have to be 
recorded and should be reviewable for minimum of 6 months. 
 
1.5.31. All production and DR server administrator sessions shall be accessed through 
Privileged Access Management (PAM) solution. 
 
1.5.32. The production system super user password request from administrators shall be 
approved by Head of IT. This should be done based on the merit of the requirement. 
 
1.5.33. The operating system user ID creation request must be approved by Head of IT  
 
1.5.34. The access to the operating system and services should be based on “need basis” and 
should be restricted. 
 
1.5.35. The super user ID should be used only if necessary. If the task can be carried out by a 
normal user, it should be done so. 
 
1.5.36. The access of the home directory of each user should be restricted to the user and the 
system administrator. 
 
1.5.37. Developers and testers should not have access to production server. Any exception 
has to be approved and recorded. 
 
1.5.38. Trusted user logins should be avoided. If required, it should be limited with proper 
documentation. 
 


--- Page 6 ---

 
Document Title 
Operating System Management and Access Control Standard 
Document ID 
ISDP/STD.08 
Effective Date 
29-NOV-2024 
 
ISC/STD.08 
Revision 10 (29-NOV-2024) 
Page 6 of 10  
1.5.39. Users and groups should be reviewed quarterly and unwanted users / groups should 
be deleted. A record must be kept for any such deletions. 
 
1.5.40. Services and application accounts that are not relevant / not being used should be 
disabled / removed wherever practical. 
 
1.5.41. Remote access to production systems (for vendors) should be discouraged. In case of 
any exception, the same shall be approved and the actions must be recorded. Actions 
should be available for review for minimum of 6 months. 
 
Maintenance and Monitoring: 
1.5.42. System Administrators are responsible for day-to-day management and maintenance 
of operating system. 
 
1.5.43. System administrators are responsible for monitoring and reporting of system 
performance. 
 
1.5.44. After office hours monitoring and recording of system performance on defined criteria 
would be done by IT operation desk. In case of any abnormality, the operators should 
follow the escalation procedure. 
 
1.5.45. The performance data of the systems have to be studied and if relevant, third party 
vendors have to be involved in the process. 
 
1.5.46. All production operating systems and related software must have necessary vendor 
support. 
 
1.5.47. Any operating system issue which needs to be escalated to the vendor support has to 
be done by the System Administrator / IT infrastructure Manager. 
 
1.5.48. IT infrastructure manager is supposed to review the status of escalated issues and 
provide necessary help to the technical team in escalating to next level and arranging 
a solution. 
 
1.5.49. Any scheduled downtime required should be approved by Head of IT. 
 
1.5.50. Approved maintenance schedules should be published to users if it is going to affect 
the normal operations. 
 
1.5.51. All system / service downtimes should be recorded by system administrator / operators. 
 
1.5.52. It is highly advisable to have a full system backup before any critical maintenance 
activity. 
 
1.5.53. Any external vendor activities in the datacenter should be monitored by the staff 
concerned. 
 
1.5.54. System Administrators / Operators have to follow the backup policy to ensure the 
availability of data. 


--- Page 7 ---

 
Document Title 
Operating System Management and Access Control Standard 
Document ID 
ISDP/STD.08 
Effective Date 
29-NOV-2024 
 
ISC/STD.08 
Revision 10 (29-NOV-2024) 
Page 7 of 10  
 
1.5.55. All system logs have to be backed up regularly. The system logs should not be trimmed 
/ deleted without taking the backup.  
 
1.5.56. All critical servers shall forward security event logs to centralized log management 
device / solution (e.g. SIEM). Such solutions should retain the logs for at least one year, 
with a minimum of three months period online (for immediate availability for analysis). 
 
1.5.57. User home directories should be maintained regularly. 
 
Licensing and Documentation 
1.5.58. System administrators to maintain the license entitlements of the OS and related 
applications. 
 
1.5.59. Inventory of licenses (operating system and related services) have to be reviewed and 
updated regularly (minimum once a year). 
 
1.5.60. System administrators to maintain the list of production and test servers. 
 
1.5.61. System administrators are responsible to create and maintain related documentation. 
 
1.5.62. Vendor supplied documents must be maintained by the system administrators. 
 
1.6 
Policy / Procedure / Authority Matrix Interactions or Connections  
 
This standard is a part of bank’s overarching Information Security Management System (ISMS) Policy 
ISDP/POL.01). 
 
1.7 
Annexure / Attachments / Supporting Documents  
 
• 
IT Inventory 
• 
License Inventory 
 
1.8 
Key Controls / Management Reports 
 
Monthly management report on system availability 
 
 
 
 
 
 
 
 
 
 
 


--- Page 8 ---

 
Document Title 
Operating System Management and Access Control Standard 
Document ID 
ISDP/STD.08 
Effective Date 
29-NOV-2024 
 
ISC/STD.08 
Revision 10 (29-NOV-2024) 
Page 8 of 10  
2. Approval Sign-off 
Prepared by (a): Initiator Section 
Name 
Designation 
Department 
Date  
Signature 
Rajesh Balakrishnan 
Senior Manager 
ISDP Department 
15-NOV-2024 
SD 
 
 
 
 
 
Reviewed by (b): Stakeholder Section 
Name 
Designation 
Department 
Date 
Signature 
Jayamohan VD 
Head of IT 
Information 
Technology 
17-NOV-2024 
SDS 
Raghavendran Gopal 
Manager 
Operations Risk 
20-NOV-2024 
SD 
 
 
 
 
 
Reviewed by (c): Mandatory Reviewer Section 
Name  
Designation 
 
Department 
 
Date 
 
Signature 
Ahmed Al Mulla 
Acting Head of 
Legal 
Legal  
21-NOV-2024 
SD 
Claudia Linca 
Head of 
Compliance 
Senior Management 
27-NOV-2024 
SD 
Venkatrao Patnaik 
CRO 
Senior Management 
28-NOV-2024 
SD 


--- Page 9 ---

 
Document Title 
Operating System Management and Access Control Standard 
Document ID 
ISDP/STD.08 
Effective Date 
29-NOV-2024 
 
ISC/STD.08 
Revision 10 (29-NOV-2024) 
Page 9 of 10  
Konattu G. Pradeep 
CFO / ACOO 
Senior Management 
29-NOV-2024 
SD 
 
 
 
 
 
Reviewed by (d): Policy and Procedure Control unit 
Name 
Designation 
 
Department 
 
Date 
 
Signature 
Shafaq Aqil 
Assistant Manager 
Policies & 
Procedures 
29-NOV-2024 
SD 
 
 
 
 
 
Approved by (e): Approver Section 
Name 
Designation 
Department 
Date 
Signature 
Adnan Al Awadhi 
CEO 
Executive 
Management 
29-NOV-2024 
SD 
 
 
*Note: Guidelines on signing authorities are as follows: 
Section (a): Initiator signoff to be signed by document owner, i.e. Head of the Department 
Section (b): Stakeholder signoff to be signed by Heads of Department whose processes are directly impacted by this document 
Section (c): Mandatory Reviewer signoff to be signed by Head of Department Legal and Senior Management Team, i.e. CFO/ ACOO, Head 
of Risk and Head of Compliance  
Section (d): Review and clearance by PPC Unit for document control.  
Section (e): Approver section to be signed by the final approver/s of this document, i.e. CEO and/or Board or Board Committee, as 
applicable 
 
 
 
 
 
 
 
 
 
 


--- Page 10 ---

 
Document Title 
Operating System Management and Access Control Standard 
Document ID 
ISDP/STD.08 
Effective Date 
29-NOV-2024 
 
ISC/STD.08 
Revision 10 (29-NOV-2024) 
Page 10 of 10  
3.   Revision Log 
 
Revision 
No. 
Revision 
Date 
Section 
Change Description 
01 
21-MAY-2008 
 
Original document 
02 
08-FEB-2010 
 
Review and update 
03 
15-FEB-2010 
 
Review and update 
04 
30-SEP-2014 
 
Review and update 
05 
07-DEC-2014 
 
Review and update 
06 
01-FEB-2015 
 
Review and update 
07 
18-JAN-2021 
 
Annual Review 
08 
10-NOV-2022 
 
Review and change in document format 
09 
30-Nov-2023 
1.1 
Added clause on document ownership and 
responsibility 
2.d 
Added PMO as interim PPC Unit reviewer   
All 
• Department name changed from “Information 
Security and Compliance” to “Information Security 
and Data Protection” 
• Format changes and document version update 
10 
29-Nov-2024 
All 
• Changed PMO name under PPC reviewer   
• Document version updated in all standards 
 
