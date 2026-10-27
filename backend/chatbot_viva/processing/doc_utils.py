"""Utilities for legal document naming and domain extraction."""

import os
import re


def get_legal_doc_name(source: str) -> str:
    """Extract human-readable name from legal document file path/name."""
    filename = (
        os.path.basename(source)
        if os.path.sep in source or '/' in source
        else source
    )
    filename = re.sub(r'\.md$', '', filename, flags=re.IGNORECASE)
    filename = filename.replace('_', ' ')

    match = re.match(
        r'^(\d+)\s+(\d{4})\s+(ND|TT|QD|QH)\s*-?\s*(\w+)',
        filename, re.IGNORECASE,
    )
    if match:
        num = match.group(1)
        year = match.group(2)
        doc_type = match.group(3).upper()
        issuer = match.group(4).upper()

        type_names = {
            'ND': 'Nghị định',
            'TT': 'Thông tư',
            'QD': 'Quyết định',
            'QH': 'Luật'
        }
        doc_name = type_names.get(doc_type, doc_type)
        return f"{doc_name} {num}/{year}/{doc_type}-{issuer}"

    if filename.lower().startswith(
            'nghị định') or filename.lower().startswith('nghi dinh'):
        return filename.title()
    if filename.lower().startswith('thông tư') or filename.lower().startswith('thong tu'):
        return filename.title()
    if filename.lower().startswith('luật') or filename.lower().startswith('luat'):
        return filename.title()

    return filename.title()


def get_domain_name(url: str) -> str:
    """Extract readable domain name from URL."""
    try:
        match = re.search(r'https?://(?:www\.)?([^/]+)', url)
        if match:
            domain = match.group(1)
            domain = re.sub(r'\.(com|vn|org|net|gov|edu).*$', '', domain)
            return domain.replace('.', ' ').title()
        return url
    except Exception:
        return url
