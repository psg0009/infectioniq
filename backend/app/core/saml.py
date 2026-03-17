"""
SSO/SAML Support
Provides SAML 2.0 AuthnRequest generation and response parsing.
Uses basic XML handling (no external SAML library required).
"""

import base64
import uuid
import zlib
from datetime import datetime, timedelta
from typing import Optional, Dict
from dataclasses import dataclass
import xml.etree.ElementTree as ET
import logging

from app.config import settings

logger = logging.getLogger(__name__)

SAML_NS = "urn:oasis:names:tc:SAML:2.0:assertion"
SAMLP_NS = "urn:oasis:names:tc:SAML:2.0:protocol"


@dataclass
class SSOConfig:
    entity_id: str
    sso_url: str
    slo_url: str
    x509_cert: str
    sp_entity_id: str
    acs_url: str


def get_sso_config() -> Optional[SSOConfig]:
    """Get SSO configuration from settings"""
    if not settings.SSO_ENABLED:
        return None
    return SSOConfig(
        entity_id=settings.SSO_ENTITY_ID,
        sso_url=settings.SSO_SSO_URL,
        slo_url=settings.SSO_SLO_URL,
        x509_cert=settings.SSO_X509_CERT,
        sp_entity_id=settings.SSO_SP_ENTITY_ID,
        acs_url=settings.SSO_ACS_URL,
    )


def create_authn_request(config: SSOConfig) -> str:
    """Create a SAML AuthnRequest and return as base64-encoded deflated XML"""
    request_id = f"_id-{uuid.uuid4()}"
    issue_instant = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    xml = f"""<samlp:AuthnRequest
        xmlns:samlp="{SAMLP_NS}"
        xmlns:saml="{SAML_NS}"
        ID="{request_id}"
        Version="2.0"
        IssueInstant="{issue_instant}"
        Destination="{config.sso_url}"
        AssertionConsumerServiceURL="{config.acs_url}"
        ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">
        <saml:Issuer>{config.sp_entity_id}</saml:Issuer>
    </samlp:AuthnRequest>"""

    deflated = zlib.compress(xml.encode())[2:-4]  # raw deflate
    return base64.b64encode(deflated).decode()


def parse_saml_response(saml_response_b64: str) -> Optional[Dict[str, str]]:
    """Parse a SAML Response and extract user attributes"""
    try:
        xml_bytes = base64.b64decode(saml_response_b64)
        root = ET.fromstring(xml_bytes)

        ns = {"saml": SAML_NS, "samlp": SAMLP_NS}

        # Check status
        status_code = root.find(".//samlp:StatusCode", ns)
        if status_code is not None:
            if "Success" not in status_code.get("Value", ""):
                logger.warning("SAML response status is not Success")
                return None

        # Extract attributes
        attributes = {}
        for attr in root.findall(".//saml:Attribute", ns):
            name = attr.get("Name", "")
            value_el = attr.find("saml:AttributeValue", ns)
            if value_el is not None and value_el.text:
                # Map common attribute names
                key = name.split("/")[-1] if "/" in name else name
                attributes[key] = value_el.text

        # Extract NameID
        name_id = root.find(".//saml:NameID", ns)
        if name_id is not None and name_id.text:
            attributes["email"] = name_id.text

        return attributes if attributes else None

    except Exception as e:
        logger.error(f"Failed to parse SAML response: {e}")
        return None


def generate_sp_metadata(config: SSOConfig) -> str:
    """Generate SP metadata XML"""
    return f"""<?xml version="1.0"?>
<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"
    entityID="{config.sp_entity_id}">
    <md:SPSSODescriptor
        AuthnRequestsSigned="false"
        WantAssertionsSigned="true"
        protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
        <md:AssertionConsumerService
            Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
            Location="{config.acs_url}"
            index="0" isDefault="true"/>
    </md:SPSSODescriptor>
</md:EntityDescriptor>"""
