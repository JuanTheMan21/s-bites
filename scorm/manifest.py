"""SCORM 1.2 ``imsmanifest.xml`` -- the minimum a compliant LMS needs to import and launch a
single-SCO course: identifiers, one organization/item pointing at the launch page, and the
resource file list.

SCORM 1.2 rather than 2004: it is the more widely supported target across LMSs, and this
package's whole scope is "play one video, report completion" -- 2004's richer sequencing model
has nothing to express here that 1.2 cannot.
"""

from xml.sax.saxutils import escape

SCORM_VERSION = "1.2"


def build_manifest(*, job_id: str, title: str, launch_file: str, resource_files: list[str]) -> str:
    """One ``<organization>`` containing one ``<item>`` -- all SCORM 1.2 requires for a course
    that is just "play this video," with no branching or multi-SCO sequencing to express.
    """
    safe_title = escape(title)
    file_entries = "\n".join(f'      <file href="{escape(name)}"/>' for name in resource_files)
    return f"""<?xml version="1.0" standalone="no" ?>
<manifest identifier="s-bites-{job_id}" version="1"
    xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
    xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.imsproject.org/xsd/imscp_rootv1p1p2 imscp_rootv1p1p2.xsd
                        http://www.adlnet.org/xsd/adlcp_rootv1p2 adlcp_rootv1p2.xsd">
  <metadata>
    <schema>ADL SCORM</schema>
    <schemaversion>{SCORM_VERSION}</schemaversion>
  </metadata>
  <organizations default="s-bites-org-{job_id}">
    <organization identifier="s-bites-org-{job_id}">
      <title>{safe_title}</title>
      <item identifier="item-1" identifierref="resource-1">
        <title>{safe_title}</title>
      </item>
    </organization>
  </organizations>
  <resources>
    <resource identifier="resource-1" type="webcontent" adlcp:scormtype="sco" href="{escape(launch_file)}">
{file_entries}
    </resource>
  </resources>
</manifest>
"""
