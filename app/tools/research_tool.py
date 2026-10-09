import json
import re
import urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from app.config import Config
from app.models.database import Database

# Verified authoritative reference sources for foundational technology domains
AUTHENTIC_KNOWLEDGE_BASE = {
    "cloud computing": {
        "canonical_title": "Cloud Computing",
        "direct_answer": (
            "Cloud computing is the on-demand delivery of IT resources over "
            "the Internet with pay-as-you-go pricing. Instead of buying, "
            "owning, and maintaining physical data centers and servers, "
            "organizations access technology services such as compute power, "
            "storage, and databases on an as-needed basis from cloud providers."
        ),
        "executive_summary": (
            "Cloud computing transforms computational infrastructure into a "
            "metered utility. It provides rapid elasticity, broad network "
            "access, resource pooling, and service models including IaaS, "
            "PaaS, and SaaS."
        ),
        "key_concepts": [
            "IaaS (Infrastructure as a Service): Renting fundamental computing infrastructure such as VMs, storage, and virtual networks.",
            "PaaS (Platform as a Service): Hardware and software tools provided over the internet for application development.",
            "SaaS (Software as a Service): Complete, vendor-managed application delivered over web browsers.",
            "Deployment Models: Public Cloud, Private Cloud, and Hybrid Cloud.",
            "Core Attributes: On-demand self-service, broad network access, resource pooling, rapid elasticity, and measured service."
        ],
        "important_findings": [
            "Cloud computing enables organizations to provision computing resources on demand rather than maintaining all infrastructure themselves.",
            "The shared responsibility model separates provider security responsibilities from customer responsibilities.",
            "Multi-region architectures can improve resilience and availability when designed correctly."
        ],
        "benefits": [
            "Agility and elasticity: resources can be provisioned and scaled according to demand.",
            "Cost optimization: organizations can reduce large upfront infrastructure expenditure.",
            "Global reach: applications can be deployed across geographically distributed infrastructure.",
            "Reliability and redundancy: cloud platforms provide mechanisms for backup, recovery, and failover."
        ],
        "risks": [
            "Data sovereignty and compliance requirements can affect where data may be stored and processed.",
            "Vendor lock-in can make migration between providers difficult.",
            "Security misconfiguration can expose applications or data."
        ],
        "real_world_examples": [
            "Amazon Web Services provides services such as EC2, S3, and Lambda.",
            "Google Cloud provides services such as Google Kubernetes Engine and BigQuery.",
            "Netflix uses cloud infrastructure for large-scale streaming services."
        ],
        "actionable_next_steps": [
            "Learn the fundamentals of cloud computing and the major service models.",
            "Practice provisioning compute and networking resources.",
            "Build a small web application using cloud infrastructure."
        ],
        "sources": [
            {
                "title": "NIST Special Publication 800-145: The NIST Definition of Cloud Computing",
                "authors": "Peter Mell, Timothy Grance",
                "year": "2011",
                "source_type": "Government Standard (NIST)",
                "url": "https://csrc.nist.gov/publications/detail/sp/800-145/final",
                "snippet": (
                    "Defines cloud computing through five essential characteristics, "
                    "three service models, and four deployment models."
                ),
                "verification_status": "SOURCE VERIFIED"
            },
            {
                "title": "ISO/IEC 17788: Information Technology — Cloud Computing — Overview and Vocabulary",
                "authors": "ISO/IEC JTC 1/SC 38",
                "year": "2014",
                "source_type": "International Standard (ISO)",
                "url": "https://www.iso.org/standard/60544.html",
                "snippet": (
                    "Provides terminology and an overview of cloud computing concepts."
                ),
                "verification_status": "SOURCE VERIFIED"
            }
        ]
    },

    "java collections framework": {
        "canonical_title": "Java Collections Framework",
        "direct_answer": (
            "The Java Collections Framework is a unified architecture for "
            "representing and manipulating collections in the Java standard "
            "library. It provides interfaces such as List, Set, Queue, Deque, "
            "and Map together with concrete implementations such as ArrayList, "
            "LinkedList, HashSet, TreeSet, HashMap, and TreeMap."
        ),
        "executive_summary": (
            "The Java Collections Framework provides standardized data "
            "structures and algorithms that reduce programming effort and "
            "allow developers to select implementations appropriate to "
            "different performance and usage requirements."
        ),
        "key_concepts": [
            "List: Ordered collection that can contain duplicate elements.",
            "Set: Collection designed to prevent duplicate elements.",
            "Map: Key-value data structure where keys identify values.",
            "Queue and Deque: Structures for processing elements in ordered or double-ended workflows.",
            "Common implementations include ArrayList, LinkedList, HashSet, TreeSet, HashMap, TreeMap, PriorityQueue, and ArrayDeque."
        ],
        "important_findings": [
            "Different collection implementations provide different performance characteristics and should be selected according to the use case.",
            "HashMap provides hash-based key-value lookup while TreeMap maintains keys in sorted order.",
            "Standard Java collections require appropriate handling when used concurrently."
        ],
        "benefits": [
            "Software reusability through standard data structures.",
            "Consistent APIs across different collection implementations.",
            "Efficient implementations for common data-management operations."
        ],
        "risks": [
            "Many standard collection implementations are not inherently thread-safe.",
            "Incorrect equals() and hashCode() implementations can cause problems with hash-based collections.",
            "Boxing primitive values into wrapper objects can introduce memory overhead."
        ],
        "real_world_examples": [
            "ArrayList can store database records retrieved for processing.",
            "HashMap can store user session or configuration information.",
            "PriorityQueue can be used in task scheduling systems."
        ],
        "actionable_next_steps": [
            "Practice deduplication using HashSet.",
            "Practice frequency counting using HashMap.",
            "Learn concurrent collection classes such as ConcurrentHashMap."
        ],
        "sources": [
            {
                "title": "Oracle Java SE Documentation: Collections Framework Overview",
                "authors": "Oracle Corporation",
                "year": "2024",
                "source_type": "Official Technical Documentation",
                "url": "https://docs.oracle.com/javase/8/docs/technotes/guides/collections/overview.html",
                "snippet": (
                    "Documentation covering collection interfaces, implementations, "
                    "algorithms, and design."
                ),
                "verification_status": "SOURCE VERIFIED"
            },
            {
                "title": "Effective Java, 3rd Edition",
                "authors": "Joshua Bloch",
                "year": "2018",
                "source_type": "Authoritative Technical Book",
                "url": "https://www.oreilly.com/library/view/effective-java-3rd/9780134686097/",
                "snippet": (
                    "Discusses best practices for Java collections, interfaces, "
                    "equals/hashCode, and concurrency."
                ),
                "verification_status": "SOURCE VERIFIED"
            }
        ]
    },

    "ai agents in education": {
        "canonical_title": "AI Agents in Education",
        "direct_answer": (
            "AI agents in education are software systems that can understand "
            "goals, assist learners and educators, personalize interactions, "
            "and coordinate multi-step educational workflows with appropriate "
            "human oversight."
        ),
        "executive_summary": (
            "Educational AI agents can move beyond simple question-answering "
            "by helping users organize goals, provide guidance, and coordinate "
            "learning activities. Human oversight remains important for "
            "academic integrity, privacy, and reliability."
        ),
        "key_concepts": [
            "Intelligent Tutoring Systems can provide personalized learning support.",
            "Autonomous Study Planning can decompose learning goals into manageable activities.",
            "Socratic Scaffolding guides learners through questions rather than simply providing answers.",
            "Human-in-the-Loop Oversight keeps important educational decisions under user control."
        ],
        "important_findings": [
            "AI systems in education can provide personalized assistance and feedback.",
            "Human oversight is important when AI systems make recommendations or perform actions.",
            "Ungrounded generative AI can produce incorrect information and therefore requires appropriate verification."
        ],
        "benefits": [
            "Personalized learning support.",
            "Continuous availability for basic academic assistance.",
            "Potential to identify scheduling conflicts and workload issues."
        ],
        "risks": [
            "Academic integrity concerns.",
            "Student data privacy concerns.",
            "Hallucinated or incorrect information from generative AI systems."
        ],
        "real_world_examples": [
            "Intelligent tutoring systems.",
            "AI-assisted educational platforms.",
            "AI tutors that provide guided feedback."
        ],
        "actionable_next_steps": [
            "Use educational AI as a learning assistant rather than an automatic assignment writer.",
            "Keep human approval for important educational decisions and actions.",
            "Verify important academic information using reliable sources."
        ],
        "sources": [
            {
                "title": "Guidance for Generative AI in Education and Research",
                "authors": "UNESCO",
                "year": "2023",
                "source_type": "International Policy Guidance",
                "url": "https://www.unesco.org/en/articles/guidance-generative-ai-education-and-research",
                "snippet": (
                    "Provides guidance on responsible use of generative AI "
                    "in education and research."
                ),
                "verification_status": "SOURCE VERIFIED"
            }
        ]
    }
}


class ResearchTool:

    @staticmethod
    def extract_canonical_topic(raw_query):
        """Normalize a research request while preserving its main subject."""
        if not raw_query:
            return ""

        clean = re.sub(r"\s+", " ", raw_query.strip())
        clean = re.sub(r"[?!.]+$", "", clean).strip()

        # Normalize common comparison wording before generic prefix removal.
        lower = clean.lower()
        if (
            "cloud computing" in lower
            and "edge computing" in lower
            and any(word in lower for word in ("compare", "difference", "versus", " vs ", "vs."))
        ):
            return "Cloud Computing vs Edge Computing"

        patterns = [
            r"^(?:please\s+)?(?:tell\s+me\s+about\s+(?:the\s+)?|what\s+is\s+(?:the\s+)?|what\s+are\s+(?:the\s+)?|explain\s+(?:the\s+)?|overview\s+of\s+(?:the\s+)?|research\s+(?:on\s+|about\s+|the\s+)?|describe\s+(?:the\s+)?|define\s+(?:the\s+)?|can\s+you\s+explain\s+(?:the\s+)?|pros\s+and\s+cons\s+of\s+|advantages\s+and\s+disadvantages\s+of\s+)",
        ]
        for pattern in patterns:
            clean = re.sub(pattern, "", clean, flags=re.IGNORECASE).strip()

        return clean.strip(" .?")

    @staticmethod
    def query_live_wikipedia(topic):
        """Fetch a Wikipedia result only when it is clearly relevant.

        Wikipedia is a supplementary source, not a guarantee of academic
        authority. Irrelevant results are rejected by checking title overlap.
        """
        if not topic:
            return None

        try:
            encoded_query = urllib.parse.quote(topic)
            search_url = (
                "https://en.wikipedia.org/w/api.php"
                f"?action=query&list=search&srsearch={encoded_query}&format=json"
            )
            headers = {
                "User-Agent": (
                    "TaskPilot-AI-Agent/2.0 "
                    "(Academic Research; Education Assistant)"
                )
            }

            response = requests.get(search_url, headers=headers, timeout=5)
            if not response.ok:
                return None

            results = response.json().get("query", {}).get("search", [])
            if not results:
                return None

            # Reject results that don't overlap with the requested subject.
            topic_terms = {
                term for term in re.findall(r"[a-zA-Z]{3,}", topic.lower())
                if term not in {
                    "what", "about", "explain", "compare", "comparison",
                    "difference", "differences", "between", "advantages",
                    "disadvantages", "real", "world", "examples", "using",
                    "reliable", "sources", "cloud", "computing", "edge"
                }
            }
            selected = None
            for item in results[:5]:
                title = item.get("title", "")
                title_terms = set(re.findall(r"[a-zA-Z]{3,}", title.lower()))
                if topic_terms and topic_terms.intersection(title_terms):
                    selected = item
                    break

            # For cloud/edge comparisons, a generic unrelated page is not useful.
            if selected is None:
                return None

            title = selected["title"]
            page_slug = urllib.parse.quote(title.replace(" ", "_"))
            summary_url = (
                "https://en.wikipedia.org/api/rest_v1/page/summary/"
                f"{page_slug}"
            )
            summary_response = requests.get(
                summary_url, headers=headers, timeout=5
            )
            if not summary_response.ok:
                return None

            summary_data = summary_response.json()
            extract = summary_data.get("extract", "")
            page_url = (
                summary_data.get("content_urls", {})
                .get("desktop", {})
                .get("page", f"https://en.wikipedia.org/wiki/{page_slug}")
            )
            if not extract:
                return None

            return {
                "title": title,
                "extract": extract,
                "url": page_url,
                "source": {
                    "title": f"Wikipedia Article: {title}",
                    "authors": "Wikimedia Foundation Contributors",
                    "year": str(datetime.now(ZoneInfo(Config.TIMEZONE)).year),
                    "source_type": "Open Encyclopedia",
                    "url": page_url,
                    "snippet": extract[:280] + ("..." if len(extract) > 280 else ""),
                    "verification_status": "LIVE PAGE RETRIEVED"
                }
            }
        except Exception:  # noqa: BLE001 — Optional live research must fall back gracefully.
            return None

    @staticmethod
    def search_information(query, max_results=5):
        """Return topic-relevant sources and avoid unrelated search results."""
        if not query or not query.strip():
            raise ValueError("Query string cannot be empty")

        clean_topic = ResearchTool.extract_canonical_topic(query)
        clean_lower = clean_topic.lower()
        sources = []

        # Handle comparison questions by selecting sources for both concepts.
        if "cloud computing" in clean_lower and "edge computing" in clean_lower:
            for key in ("cloud computing",):
                sources.extend(AUTHENTIC_KNOWLEDGE_BASE.get(key, {}).get("sources", []))

            sources.append({
                "title": "Cloudflare Learning Center: What Is Edge Computing?",
                "authors": "Cloudflare",
                "year": "",
                "source_type": "Technology Explainer",
                "url": "https://www.cloudflare.com/learning/serverless/glossary/what-is-edge-computing/",
                "snippet": (
                    "Reference page about edge computing. Open the source to "
                    "review its definition, architecture, and use cases."
                ),
                "verification_status": "REFERENCE LINK — CONTENT NOT FETCHED"
            })

        else:
            matched_entry = None
            for key, entry in AUTHENTIC_KNOWLEDGE_BASE.items():
                if key in clean_lower or clean_lower in key:
                    matched_entry = entry
                    break

            if matched_entry:
                sources.extend(matched_entry.get("sources", []))

        # Only append a live Wikipedia source if its title passed relevance checks.
        live_wiki = ResearchTool.query_live_wikipedia(clean_topic)
        if live_wiki:
            wiki_source = live_wiki["source"]
            if not any(s.get("url") == wiki_source.get("url") for s in sources):
                sources.append(wiki_source)

        # Deduplicate by URL and preserve order.
        unique_sources = []
        seen_urls = set()
        for source in sources:
            url = source.get("url", "").strip()
            if url and url not in seen_urls:
                unique_sources.append(source)
                seen_urls.add(url)

        return {
            "query": query,
            "canonical_topic": clean_topic,
            "provider": "TaskPilot curated references and relevance-filtered retrieval",
            "sources": unique_sources[:max_results]
        }

    @staticmethod
    def summarize_information(query, sources=None):
        """Synthesize a research answer with quota-aware Gemini and a safe fallback."""
        clean_topic = ResearchTool.extract_canonical_topic(query)

        if sources is None:
            sources = ResearchTool.search_information(query).get("sources", [])

        # Filter out sources that do not match a comparison topic.
        topic_lower = clean_topic.lower()
        if "cloud computing" in topic_lower and "edge computing" in topic_lower:
            allowed = ("nist.gov", "iso.org", "cloudflare.com")
            sources = [
                source for source in sources
                if any(domain in source.get("url", "").lower() for domain in allowed)
            ]

        source_material = [
            {
                "title": source.get("title", ""),
                "authors": source.get("authors", ""),
                "year": source.get("year", ""),
                "source_type": source.get("source_type", ""),
                "url": source.get("url", ""),
                "snippet": source.get("snippet", "")
            }
            for source in sources
        ]
        source_text = json.dumps(source_material, indent=2, ensure_ascii=False)

        prompt = f"""
You are the Research Agent inside TaskPilot AI.

Research question: {query}
Canonical topic: {clean_topic}

Source material retrieved by TaskPilot:
{source_text}

Rules:
- Answer the user's actual question.
- Treat the supplied source snippets as evidence; do not claim to have read page content that is not included.
- Never invent sources, URLs, authors, statistics, quotations, or research findings.
- Do not cite any source that is not in the supplied source material.
- If the supplied snippets do not establish a detail, label it as general background or say that the available source material does not establish it.
- For comparison questions, compare both subjects explicitly.
- Write for a college student.
- Return ONLY valid JSON, with no Markdown fences.

Return this exact structure:
{{
  "direct_answer": "Direct answer",
  "executive_summary": "Concise summary",
  "key_concepts": ["Concept 1", "Concept 2"],
  "findings": ["Supported finding 1", "Supported finding 2"],
  "benefits": ["Benefit 1"],
  "risks": ["Risk 1"],
  "real_world_examples": ["Example 1"],
  "action_items": ["Next step 1"]
}}
"""

        # Defaults are replaced by a topic-specific, clearly labelled fallback
        # if Gemini is unavailable or the project quota has been exhausted.
        ai_generated = False
        gemini_error = None

        try:
            # Local import prevents the research_tool/services circular import.
            from app.services.gemini_service import GeminiService

            client = GeminiService.get_client()
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt
            )
            raw_text = (response.text or "").strip()

            if raw_text.startswith("```"):
                raw_text = re.sub(
                    r"^```(?:json)?\s*", "", raw_text, flags=re.IGNORECASE
                )
                raw_text = re.sub(r"\s*```$", "", raw_text).strip()

            result = json.loads(raw_text)

            required_fields = (
                "direct_answer", "executive_summary", "key_concepts",
                "findings", "benefits", "risks",
                "real_world_examples", "action_items"
            )
            if not all(field in result for field in required_fields):
                raise ValueError("Gemini response is missing required JSON fields")

            direct_answer = str(result["direct_answer"])
            executive_summary = str(result["executive_summary"])
            key_concepts = result["key_concepts"] if isinstance(result["key_concepts"], list) else []
            important_findings = result["findings"] if isinstance(result["findings"], list) else []
            benefits = result["benefits"] if isinstance(result["benefits"], list) else []
            risks = result["risks"] if isinstance(result["risks"], list) else []
            real_world_examples = result["real_world_examples"] if isinstance(result["real_world_examples"], list) else []
            actionable_next_steps = result["action_items"] if isinstance(result["action_items"], list) else []
            ai_generated = True

        except Exception as error:  # noqa: BLE001 — Gemini failures must activate the local fallback.
            gemini_error = str(error)
            error_text = gemini_error.lower()

            # A 429 quota error will not be fixed by immediate retries.
            if "429" in error_text or "resource_exhausted" in error_text or "quota" in error_text:
                print("⚠️ Gemini quota is exhausted. Using TaskPilot's local fallback.")
            elif "503" in error_text or "unavailable" in error_text:
                print("⚠️ Gemini is temporarily unavailable. Using TaskPilot's local fallback.")
            else:
                print(f"⚠️ Gemini synthesis failed. Using local fallback: {gemini_error}")

            # This fallback uses only foundational definitions already held by
            # TaskPilot and clearly notes that it is not a Gemini-generated answer.
            if "cloud computing" in topic_lower and "edge computing" in topic_lower:
                direct_answer = (
                    "Cloud computing and edge computing are complementary approaches. "
                    "Cloud computing uses centralized provider infrastructure to offer "
                    "on-demand compute, storage, and other services. Edge computing "
                    "processes data closer to where it is generated, which can reduce "
                    "the distance data must travel and may help latency-sensitive systems. "
                    "The retrieved references include NIST's cloud-computing definition "
                    "and a Cloudflare edge-computing reference page; the edge page's "
                    "content was not fetched during this run."
                )
                executive_summary = (
                    "Cloud computing is suited to elastic, centralized services and "
                    "large-scale storage or processing. Edge computing places some "
                    "processing nearer to devices or users to support responsiveness "
                    "and reduce unnecessary data transfer. They are often used together. "
                    "This is TaskPilot's built-in fallback summary, not a Gemini synthesis."
                )
                key_concepts = [
                    "Cloud computing: on-demand access to shared computing resources over a network.",
                    "Edge computing: processing data near the source of data generation or consumption.",
                    "Latency: edge processing may reduce round-trip delay for time-sensitive workloads.",
                    "Architecture: edge and cloud can work together rather than being mutually exclusive."
                ]
                important_findings = [
                    "NIST SP 800-145 defines cloud computing using essential characteristics, service models, and deployment models.",
                    "The Cloudflare edge-computing reference is provided as a link, but its page content was not fetched in this run.",
                    "The exact performance, cost, privacy, and reliability trade-offs depend on the system design and workload."
                ]
                benefits = [
                    "Cloud: elastic capacity, managed services, and centralized administration.",
                    "Edge: potentially lower latency, local processing, and reduced need to send every raw datum to a central cloud.",
                    "Hybrid: systems can keep time-sensitive processing at the edge and use cloud resources for aggregation or large-scale analytics."
                ]
                risks = [
                    "Cloud: network dependency, provider dependence, compliance constraints, and configuration mistakes.",
                    "Edge: distributed devices can be harder to manage, patch, physically secure, and monitor consistently.",
                    "These are general architecture considerations and are not quantified by the retrieved source snippets."
                ]
                real_world_examples = [
                    "Cloud example: hosting a web application and its database on a cloud platform.",
                    "Edge example: a factory gateway processing machine-sensor data locally to trigger a quick alert.",
                    "Combined example: a store processes camera events locally and sends selected summaries to cloud analytics."
                ]
                actionable_next_steps = [
                    "Open the NIST cloud-computing source and the Cloudflare edge-computing reference listed below.",
                    "Compare latency, bandwidth, privacy, cost, reliability, and operational complexity for your use case.",
                    "For an academic report, verify the edge-computing reference's full content before citing detailed claims."
                ]
            else:
                matched_entry = None
                for key, entry in AUTHENTIC_KNOWLEDGE_BASE.items():
                    if key in topic_lower or topic_lower in key:
                        matched_entry = entry
                        break

                if matched_entry:
                    direct_answer = matched_entry["direct_answer"]
                    executive_summary = matched_entry["executive_summary"]
                    key_concepts = list(matched_entry["key_concepts"])
                    important_findings = list(matched_entry["important_findings"])
                    benefits = list(matched_entry["benefits"])
                    risks = list(matched_entry["risks"])
                    real_world_examples = list(matched_entry["real_world_examples"])
                    actionable_next_steps = list(matched_entry["actionable_next_steps"])
                else:
                    direct_answer = (
                        f"Gemini is currently unavailable, and TaskPilot does not have "
                        f"enough topic-specific verified material to synthesize '{clean_topic}'."
                    )
                    executive_summary = (
                        "A complete synthesis could not be produced. The sources below "
                        "are shown for manual review; unsupported claims have not been added."
                    )
                    key_concepts = [f"Research topic: {clean_topic}"]
                    important_findings = [
                        "No topic-specific findings were generated because Gemini synthesis was unavailable."
                    ]
                    benefits = []
                    risks = [
                        "The available source material is insufficient for a reliable automatic summary."
                    ]
                    real_world_examples = []
                    actionable_next_steps = [
                        "Open and review the listed sources.",
                        "Retry synthesis when Gemini quota or service availability is restored."
                    ]

        now = datetime.now(ZoneInfo(Config.TIMEZONE)).isoformat()
        conn = Database.get_connection()

        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO research_queries
                (
                    topic,
                    sources_json,
                    findings_json,
                    summary,
                    action_items_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    clean_topic,
                    json.dumps(sources, ensure_ascii=False),
                    json.dumps(important_findings, ensure_ascii=False),
                    direct_answer,
                    json.dumps(actionable_next_steps, ensure_ascii=False),
                    now
                )
            )
            query_id = cursor.lastrowid
            conn.commit()

            return {
                "id": query_id,
                "topic": clean_topic,
                "direct_answer": direct_answer,
                "executive_summary": executive_summary,
                "key_concepts": key_concepts,
                "findings": important_findings,
                "benefits": benefits,
                "risks": risks,
                "real_world_examples": real_world_examples,
                "action_items": actionable_next_steps,
                "sources": sources,
                "created_at": now,
                "ai_generated": ai_generated,
                "synthesis_status": "gemini_success" if ai_generated else "fallback",
                "synthesis_error": gemini_error
            }
        finally:
            conn.close()

