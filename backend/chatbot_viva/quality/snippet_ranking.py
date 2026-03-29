"""
Snippet Ranking Engine - Tối ưu tốc độ đọc web như Perplexity.

Thay vì load nguyên trang web, engine này:
1. Lấy đoạn nhỏ nhất liên quan (300-800 ký tự)
2. Scoring và ranking snippets theo độ liên quan
3. Merge thông tin trùng lặp từ nhiều nguồn
4. Giảm token usage cho LLM

Inspired by Perplexity's snippet optimization.
"""

import heapq
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import unicodedata


@dataclass
class Snippet:
    """Một snippet đã được trích xuất và scored."""
    content: str
    source_url: str
    source_title: str
    relevance_score: float  # 0-1
    key_terms_matched: List[str]
    char_count: int
    is_duplicate: bool = False
    merged_from: List[str] = field(default_factory=list)


@dataclass
class RankedSnippets:
    """Kết quả sau khi ranking và merge snippets."""
    snippets: List[Snippet]
    total_chars: int
    token_estimate: int  # Ước tính số token
    sources_count: int
    duplicates_removed: int


class SnippetExtractor:
    """
    Module 1: Trích xuất đoạn 300-800 ký tự liên quan nhất từ content.
    """

    MIN_SNIPPET_LENGTH = 1500
    MAX_SNIPPET_LENGTH = 5000
    IDEAL_SNIPPET_LENGTH = 2000

    def extract_best_snippet(
        self,
        content: str,
        query: str,
        url: str = ""
    ) -> Snippet:
        """
        Trích xuất snippet tốt nhất từ content dựa trên query.

        Args:
            content: Nội dung gốc từ web
            query: Câu hỏi/query của user
            url: URL nguồn

        Returns:
            Snippet đã được tối ưu
        """
        # Clean content
        cleaned = self._clean_content(content)

        if len(cleaned) <= self.MAX_SNIPPET_LENGTH:
            # Content đã ngắn, giữ nguyên
            return Snippet(
                content=cleaned,
                source_url=url,
                source_title=self._extract_title(url),
                relevance_score=self._calculate_relevance(cleaned, query),
                key_terms_matched=self._find_matched_terms(cleaned, query),
                char_count=len(cleaned)
            )

        # Tìm đoạn tốt nhất
        best_snippet = self._find_best_segment(cleaned, query)

        return Snippet(
            content=best_snippet,
            source_url=url,
            source_title=self._extract_title(url),
            relevance_score=self._calculate_relevance(best_snippet, query),
            key_terms_matched=self._find_matched_terms(best_snippet, query),
            char_count=len(best_snippet)
        )

    def _clean_content(self, content: str) -> str:
        """Làm sạch content, loại bỏ noise."""
        # Loại HTML tags
        cleaned = re.sub(r'<[^>]+>', '', content)

        # Loại bỏ URLs trong text
        cleaned = re.sub(r'https?://\S+', '', cleaned)

        # Loại bỏ email
        cleaned = re.sub(r'\S+@\S+', '', cleaned)

        # Loại bỏ các pattern noise phổ biến
        noise_patterns = [
            r'Xem thêm:.*?(?=\.|$)',
            r'Đọc tiếp:.*?(?=\.|$)',
            r'Bài viết liên quan.*?(?=\.|$)',
            r'Tags?:.*?(?=\.|$)',
            r'Nguồn:.*?(?=\.|$)',
            r'\d+ lượt xem',
            r'\d+ bình luận',
            r'Chia sẻ.*?(?=\.|$)',
            r'Facebook|Twitter|Zalo',
            r'Quảng cáo',
            r'Advertisement',
        ]

        for pattern in noise_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

        # Chuẩn hóa whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = cleaned.strip()

        return cleaned

    def _find_best_segment(self, content: str, query: str) -> str:
        """Tìm đoạn văn tốt nhất match với query."""
        # Tokenize query
        query_terms = self._tokenize(query)

        # Split content thành sentences
        sentences = re.split(r'(?<=[.!?])\s+', content)

        if not sentences:
            return content[:self.MAX_SNIPPET_LENGTH]

        # Score từng sentence
        scored_sentences = []
        for i, sent in enumerate(sentences):
            score = self._score_sentence(sent, query_terms)
            scored_sentences.append((i, sent, score))

        # Sort by score
        scored_sentences.sort(key=lambda x: x[2], reverse=True)

        # Build snippet từ các sentence có score cao nhất
        # Giữ nguyên thứ tự xuất hiện trong văn bản gốc
        selected_indices = set()
        current_length = 0

        for idx, sent, score in scored_sentences:
            if score < 0.1:  # Skip sentences không liên quan
                continue

            sent_len = len(sent)
            if current_length + sent_len > self.MAX_SNIPPET_LENGTH:
                if current_length >= self.MIN_SNIPPET_LENGTH:
                    break
                continue

            selected_indices.add(idx)
            current_length += sent_len + 1  # +1 for space

            if current_length >= self.IDEAL_SNIPPET_LENGTH:
                break

        # Nếu không đủ content, lấy thêm các sentence liền kề
        if current_length < self.MIN_SNIPPET_LENGTH and selected_indices:
            min_idx = min(selected_indices)
            max_idx = max(selected_indices)

            # Thêm sentence trước và sau
            for expand in range(1, 3):
                if min_idx - expand >= 0:
                    selected_indices.add(min_idx - expand)
                    current_length += len(sentences[min_idx - expand])
                if max_idx + expand < len(sentences):
                    selected_indices.add(max_idx + expand)
                    current_length += len(sentences[max_idx + expand])
                if current_length >= self.MIN_SNIPPET_LENGTH:
                    break

        # Build final snippet theo thứ tự gốc
        if not selected_indices:
            return content[:self.MAX_SNIPPET_LENGTH]

        sorted_indices = sorted(selected_indices)
        snippet_parts = [sentences[i] for i in sorted_indices]
        snippet = ' '.join(snippet_parts)

        # Trim nếu quá dài
        if len(snippet) > self.MAX_SNIPPET_LENGTH:
            snippet = snippet[:self.MAX_SNIPPET_LENGTH].rsplit(' ', 1)[
                0] + '...'

        return snippet

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text thành các terms."""
        # Normalize Vietnamese
        normalized = unicodedata.normalize('NFC', text.lower())
        # Extract words
        words = re.findall(r'\w+', normalized)
        # Filter stopwords
        stopwords = {
            'là', 'và', 'của', 'có', 'được', 'để', 'trong', 'với',
            'cho', 'các', 'những', 'này', 'đó', 'một', 'về', 'như',
            'thì', 'mà', 'khi', 'nếu', 'còn', 'cũng', 'đã', 'sẽ',
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be',
            'have', 'has', 'had', 'do', 'does', 'did', 'will',
        }
        return [w for w in words if w not in stopwords and len(w) > 1]

    def _score_sentence(self, sentence: str, query_terms: List[str]) -> float:
        """Score một sentence dựa trên query terms."""
        if not query_terms:
            return 0.0

        sentence_lower = sentence.lower()
        sentence_terms = set(self._tokenize(sentence))

        # Term matching score
        matched = sum(1 for term in query_terms if term in sentence_lower)
        term_score = matched / len(query_terms) if query_terms else 0

        # Bonus for exact phrase match
        phrase_bonus = 0.2 if any(
            ' '.join(query_terms[i:i + 2]) in sentence_lower
            for i in range(len(query_terms) - 1)
        ) else 0

        # Bonus for legal/important keywords
        important_keywords = [
            'điều', 'khoản', 'luật', 'nghị định', 'quy định',
            'thủ tục', 'hồ sơ', 'điều kiện', 'yêu cầu',
            'triệu', 'tỷ', 'm2', '%', 'giá'
        ]
        keyword_bonus = 0.1 if any(
            kw in sentence_lower for kw in important_keywords) else 0

        # HIGH BONUS for sentences with specific numbers/data
        has_specific_data = bool(
            re.search(
                r'\d+\s*(%|triệu|tỷ|m2|năm|tháng|ngày)',
                sentence_lower))
        data_bonus = 0.25 if has_specific_data else 0

        # HIGH BONUS for sentences with legal references
        has_legal_ref = bool(
            re.search(
                r'(điều|khoản|luật|nghị định|thông tư|quyết định)\s*\d+',
                sentence_lower,
                re.IGNORECASE))
        legal_bonus = 0.4 if has_legal_ref else 0

        # Penalty for very short sentences
        length_penalty = 0 if len(sentence) > 30 else -0.2

        return min(term_score + phrase_bonus + keyword_bonus +
                   data_bonus + legal_bonus + length_penalty, 1.0)

    def _calculate_relevance(self, snippet: str, query: str) -> float:
        """Tính điểm relevance tổng thể của snippet."""
        query_terms = self._tokenize(query)
        if not query_terms:
            return 0.5

        snippet_lower = snippet.lower()
        matched = sum(1 for term in query_terms if term in snippet_lower)

        base_score = matched / len(query_terms)

        # Bonus for density of information
        info_density = len(re.findall(r'\d+', snippet)) * 0.02  # Có số liệu
        legal_density = len(re.findall(r'(Điều|Khoản|Luật)', snippet)) * 0.05

        return min(base_score + info_density + legal_density, 1.0)

    def _find_matched_terms(self, snippet: str, query: str) -> List[str]:
        """Tìm các terms từ query xuất hiện trong snippet."""
        query_terms = self._tokenize(query)
        snippet_lower = snippet.lower()
        return [term for term in query_terms if term in snippet_lower]

    def _extract_title(self, url: str) -> str:
        """Extract title/domain từ URL."""
        if not url:
            return "Unknown"
        match = re.search(r'https?://(?:www\.)?([^/]+)', url)
        return match.group(1) if match else url[:50]


class RelevanceScorer:
    """
    Module 2: Scoring và ranking các snippets.
    """

    def rank_snippets(
        self,
        snippets: List[Snippet],
        query: str,
        max_snippets: int = 5
    ) -> List[Snippet]:
        """
        Rank snippets theo độ liên quan và quality.

        Args:
            snippets: List snippets đã extract
            query: Query gốc
            max_snippets: Số snippet tối đa trả về

        Returns:
            List snippets đã sorted theo relevance
        """
        if not snippets:
            return []

        # Calculate combined score for each snippet
        scored = []
        for snippet in snippets:
            combined_score = self._calculate_combined_score(snippet, query)
            scored.append((snippet, combined_score))

        # Dùng heapq.nlargest thay sort: O(n log k) thay vì O(n log n)
        top = heapq.nlargest(max_snippets, scored, key=lambda x: x[1])

        result = []
        for snippet, score in top:
            snippet.relevance_score = score
            result.append(snippet)

        return result

    def _calculate_combined_score(self, snippet: Snippet, query: str) -> float:
        """Tính combined score từ nhiều factors."""
        # Base relevance score
        base_score = snippet.relevance_score * 0.4

        # Term coverage score
        query_terms = set(re.findall(r'\w+', query.lower()))
        coverage = len(snippet.key_terms_matched) / \
            len(query_terms) if query_terms else 0
        coverage_score = coverage * 0.3

        # Length score (prefer IDEAL_SNIPPET_LENGTH)
        ideal = 500
        length_diff = abs(snippet.char_count - ideal)
        length_score = max(0, 1 - length_diff / 500) * 0.1

        # Source credibility score
        credibility = self._get_source_credibility(snippet.source_url)
        credibility_score = credibility * 0.2

        return base_score + coverage_score + length_score + credibility_score

    def _get_source_credibility(self, url: str) -> float:
        """Đánh giá độ uy tín của nguồn."""
        if not url:
            return 0.5

        url_lower = url.lower()

        # High credibility domains
        if any(d in url_lower for d in [
               '.gov.vn', 'thuvienphapluat', 'luatvietnam', 'chinhphu']):
            return 1.0

        # Medium-high credibility
        if any(
            d in url_lower for d in [
                'vnexpress',
                'tuoitre',
                'thanhnien',
                'dantri',
                'batdongsan.com']):
            return 0.8

        # Medium credibility
        if any(d in url_lower for d in ['cafeland', 'cafef', 'vietnamnet']):
            return 0.6

        return 0.5


class SnippetMerger:
    """
    Module 3: Merge thông tin trùng lặp từ nhiều nguồn.
    """

    SIMILARITY_THRESHOLD = 0.6  # Ngưỡng để coi là duplicate

    def merge_duplicates(self, snippets: List[Snippet]) -> List[Snippet]:
        """
        Merge các snippets có nội dung trùng lặp.
        Tối ưu: pre-tokenize 1 lần thay vì O(n^2) lần.
        """
        if len(snippets) <= 1:
            return snippets

        # Pre-tokenize tất cả snippets 1 lần (tránh re-tokenize trong nested
        # loop)
        token_cache = [set(re.findall(r'\w+', s.content.lower()))
                       for s in snippets]

        merged = []
        used = set()

        for i, snippet in enumerate(snippets):
            if i in used:
                continue

            duplicates = [snippet]
            duplicate_sources = [snippet.source_url]

            for j in range(i + 1, len(snippets)):
                if j in used:
                    continue

                similarity = self._similarity_from_tokens(
                    token_cache[i], token_cache[j])

                if similarity >= self.SIMILARITY_THRESHOLD:
                    duplicates.append(snippets[j])
                    duplicate_sources.append(snippets[j].source_url)
                    used.add(j)

            if len(duplicates) > 1:
                merged_snippet = self._merge_snippets(duplicates)
                merged_snippet.merged_from = duplicate_sources
                merged.append(merged_snippet)
            else:
                merged.append(snippet)

            used.add(i)

        return merged

    @staticmethod
    def _similarity_from_tokens(words1: set, words2: set) -> float:
        """Jaccard similarity từ pre-tokenized sets."""
        if not words1 or not words2:
            return 0.0
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        return intersection / union if union > 0 else 0.0

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Tính độ tương đồng giữa 2 đoạn text (fallback)."""
        words1 = set(re.findall(r'\w+', text1.lower()))
        words2 = set(re.findall(r'\w+', text2.lower()))
        return self._similarity_from_tokens(words1, words2)

    def _merge_snippets(self, snippets: List[Snippet]) -> Snippet:
        """Merge nhiều snippets thành một."""
        # Chọn snippet có relevance cao nhất làm base
        snippets.sort(key=lambda x: x.relevance_score, reverse=True)
        base = snippets[0]

        # Collect unique information từ các snippets khác
        base_sentences = set(re.split(r'(?<=[.!?])\s+', base.content))
        additional_info = []

        for other in snippets[1:]:
            other_sentences = re.split(r'(?<=[.!?])\s+', other.content)
            for sent in other_sentences:
                # Chỉ thêm nếu sentence này mang thông tin mới
                if sent not in base_sentences:
                    is_new = all(
                        self._calculate_similarity(sent, existing) < 0.5
                        for existing in base_sentences
                    )
                    if is_new and len(sent) > 20:
                        additional_info.append(sent)
                        base_sentences.add(sent)

        # Combine content
        merged_content = base.content
        if additional_info:
            # Chỉ thêm nếu không vượt quá giới hạn
            for info in additional_info[:2]:  # Max 2 additional sentences
                if len(merged_content) + len(info) < 1000:
                    merged_content += ' ' + info

        # Combine key terms
        all_terms = set(base.key_terms_matched)
        for other in snippets[1:]:
            all_terms.update(other.key_terms_matched)

        # Average relevance score
        avg_score = sum(s.relevance_score for s in snippets) / len(snippets)

        return Snippet(
            content=merged_content,
            source_url=base.source_url,  # Keep best source as primary
            source_title=base.source_title,
            relevance_score=avg_score,
            key_terms_matched=list(all_terms),
            char_count=len(merged_content),
            is_duplicate=False,
            merged_from=[]
        )


class SnippetRankingEngine:
    """
    Engine chính - kết hợp 3 modules để tối ưu snippets.
    """

    def __init__(self):
        self.extractor = SnippetExtractor()
        self.scorer = RelevanceScorer()
        self.merger = SnippetMerger()

    def process_search_results(
        self,
        results: List[Dict],
        query: str,
        max_snippets: int = 5,
        max_total_chars: int = 2500
    ) -> RankedSnippets:
        """
        Process và optimize search results.

        Args:
            results: List kết quả từ web search (url, content)
            query: Query gốc của user
            max_snippets: Số snippet tối đa
            max_total_chars: Tổng số ký tự tối đa

        Returns:
            RankedSnippets với snippets đã tối ưu
        """
        # Step 1: Extract best snippet từ mỗi result
        snippets = []
        for result in results:
            url = result.get('url', '')
            content = result.get('content', '')

            if not content:
                continue

            snippet = self.extractor.extract_best_snippet(content, query, url)
            if snippet.char_count > 50:  # Skip snippets quá ngắn
                snippets.append(snippet)

        if not snippets:
            return RankedSnippets(
                snippets=[],
                total_chars=0,
                token_estimate=0,
                sources_count=0,
                duplicates_removed=0
            )

        # Step 2: Rank snippets
        ranked = self.scorer.rank_snippets(snippets, query, max_snippets * 2)

        # Step 3: Merge duplicates
        original_count = len(ranked)
        merged = self.merger.merge_duplicates(ranked)
        duplicates_removed = original_count - len(merged)

        # Step 4: Final selection based on total chars limit
        final_snippets = []
        total_chars = 0

        for snippet in merged:
            if len(final_snippets) >= max_snippets:
                break
            if total_chars + snippet.char_count > max_total_chars:
                # Có thể truncate snippet cuối
                remaining = max_total_chars - total_chars
                if remaining > 200:
                    snippet.content = snippet.content[:remaining - 3] + '...'
                    snippet.char_count = len(snippet.content)
                    final_snippets.append(snippet)
                    total_chars += snippet.char_count
                break

            final_snippets.append(snippet)
            total_chars += snippet.char_count

        # Estimate tokens (rough: 1 token ≈ 4 chars for Vietnamese/mixed)
        token_estimate = total_chars // 3

        return RankedSnippets(
            snippets=final_snippets,
            total_chars=total_chars,
            token_estimate=token_estimate,
            sources_count=len(set(s.source_url for s in final_snippets)),
            duplicates_removed=duplicates_removed
        )

    def format_for_llm(self, ranked: RankedSnippets) -> str:
        """
        Format ranked snippets thành string cho LLM đọc.

        Args:
            ranked: RankedSnippets đã process

        Returns:
            Formatted string tối ưu cho LLM
        """
        if not ranked.snippets:
            return "Không tìm thấy thông tin từ web."

        formatted_parts = []
        for i, snippet in enumerate(ranked.snippets, 1):
            # Compact format để tiết kiệm token
            source_note = ""
            if snippet.merged_from and len(snippet.merged_from) > 1:
                source_note = f" (+{len(snippet.merged_from)-1} nguồn khác)"

            formatted_parts.append(
                f"[{i}] {snippet.source_title}{source_note}\n"
                f"URL: {snippet.source_url}\n"
                f"{snippet.content}"
            )

        return "\n---\n".join(formatted_parts)


from chatbot_viva.core.singleton import singleton


@singleton
def get_ranking_engine() -> SnippetRankingEngine:
    """Get singleton instance của SnippetRankingEngine."""
    return SnippetRankingEngine()
