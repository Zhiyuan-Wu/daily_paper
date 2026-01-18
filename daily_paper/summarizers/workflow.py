"""
Multi-step paper summarization workflow using LLM.

This module implements a 3-step workflow for summarizing research papers.
Each step extracts specific information using dedicated prompts.

The workflow consists of 3 steps:
1. Content Summary - Comprehensive content summary (600-800 words)
2. Deep Research - Deep analysis using 5-why method (800-1000 words)
3. TLDR - One-paragraph summary (100-150 words)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from daily_paper.database import Paper, Session
from daily_paper.parsers import PDFParser
from daily_paper.summarizers.llm_client import LLMClient, LLMMessage
from daily_paper.config import Config, LLMConfig

logger = logging.getLogger(__name__)


class SummaryStep(Enum):
    """
    Enumeration of summarization workflow steps.

    Each step represents a specific type of information to extract
    from a research paper.

    3-Step Workflow:
        CONTENT_SUMMARY: Comprehensive content summary (600-800 words)
        DEEP_RESEARCH: Deep analysis using 5-why method (800-1000 words)
        TLDR: One-paragraph summary (100-150 words)
    """

    CONTENT_SUMMARY = "content_summary"
    DEEP_RESEARCH = "deep_research"
    TLDR = "tldr"

    @property
    def display_name(self) -> str:
        """Human-readable display name for the step."""
        names = {
            self.CONTENT_SUMMARY: "内容摘要",
            self.DEEP_RESEARCH: "深度研究",
            self.TLDR: "TLDR总结",
        }
        return names.get(self, self.value)

    @property
    def prompt(self) -> str:
        """Get the system prompt for this summarization step."""
        prompts = {
            self.CONTENT_SUMMARY: self._content_summary_prompt(),
            self.DEEP_RESEARCH: self._deep_research_prompt(),
            self.TLDR: self._tldr_prompt(),
        }
        return prompts.get(self, "")

    @staticmethod
    def _content_summary_prompt() -> str:
        return """你是一位专业的科研论文分析师。请对论文进行全面的综合分析，并使用中文输出：

## 分析要求

请将原有的"研究背景、核心贡献、问题陈述、技术方法、实验结果、结论与启示"整合成一个有机的整体，系统性地呈现论文的核心内容。

### 1. 研究背景
- 该研究属于哪个领域？当前领域的发展趋势和挑战是什么？
- 为什么需要这项研究？要解决的核心问题是什么？
- 现有研究的局限性和本文要填补的知识缺口

### 2. 核心贡献
- 提出了什么新方法/新模型/新理论？与现有方法的本质区别是什么？
- 理论贡献：在理论层面的突破、新框架或新范式
- 实践贡献：解决了什么实际问题？性能如何提升？开源了什么资源？

### 3. 技术方法
- 整体方法论思路和技术架构
- 关键技术组件和创新点
- 方法流程和算法细节
- 相比现有方法的技术优势

### 4. 主要结果
- 实验设置：数据集、评估指标、对比方法
- 核心实验的关键数据和性能提升
- 消融实验分析：关键组件的有效性验证
- 结果分析：为什么能取得这样的结果？

### 5. 结论与启示
- 核心结论：2-3句话总结论文的主要发现和贡献
- 研究意义：学术价值、应用价值、对后续研究的启发
- 局限性：方法的适用范围和限制条件、未解决的问题
- 未来方向：可预见的后续研究方向

## 输出格式

```markdown
# 内容摘要

## 研究背景
[1-2段描述研究领域定位、发展现状、核心问题和研究动机]

## 核心贡献
### 主要创新点
[清晰列出1-3个核心创新，说明具体是什么，与现有方法的本质区别]

### 理论与实践贡献
- **理论贡献**: [理论层面的突破]
- **实践贡献**: [解决的问题、性能提升、资源贡献]

## 技术方法
### 整体框架
[概述方法论的总体思路和技术架构]

### 关键技术
[核心技术组件、创新设计、方法流程]

## 主要结果
### 实验设置
[数据集、评估指标、对比方法]

### 核心结果
[关键数据、性能对比表格]

### 结果分析
[解释方法为什么有效，哪些设计带来了提升]

## 结论与启示
- **核心结论**: [主要发现和贡献]
- **研究意义**: [学术和应用价值]
- **局限性**: [方法限制和未解决问题]
- **未来方向**: [后续研究方向]
```

要求：
- 使用专业的学术中文表述，技术术语保留英文原文（首次出现加注释）
- 各部分逻辑连贯，形成有机整体，而非简单拼接
- 重点突出创新点和贡献
- 内容全面但精简，控制在600-800字"""

    @staticmethod
    def _deep_research_prompt() -> str:
        return """你是一位专业的科研论文深度分析师。请使用"5-why分析法"对论文的核心创新点进行深度研究，并使用中文输出：

## 5-Why分析法框架

5-why分析法是一种通过连续追问"为什么"来探究问题根本原因的深度分析方法。我们将从论文的核心创新点出发，进行5个层次的深度追问。

### 第1个Why：根本问题（Why 1 - Root Problem）
**问题：为什么需要这个核心创新？**
- 这个创新要解决的根本问题是什么？
- 这个问题为什么重要？有什么实际或理论价值？
- 不解决这个问题会带来什么后果？
- 这个问题在当前研究领域处于什么地位？

### 第2个Why：技术机制（Why 2 - Technical Mechanism）
**问题：这个创新的核心技术原理是什么？**
- 该创新如何通过技术手段解决根本问题？
- 核心技术机制是什么？如何运作？
- 为什么这个技术机制能够有效解决问题？
- 技术设计的关键洞察或突破点在哪里？

### 第3个Why：有效性来源（Why 3 - Source of Effectiveness）
**问题：为什么这个创新是有效的？**
- 该创新能够取得效果的直接原因是什么？
- 技术机制与问题解决之间的因果关系是什么？
- 为什么比现有方法更有效？本质优势在哪里？
- 理论保证或实证证据是什么？

### 第4个Why：深层价值（Why 4 - Deep Value）
**问题：这个创新的深层价值是什么？**
- 该创新对研究领域带来了什么范式性影响？
- 改变了人们对该问题的哪些认知或假设？
- 开启了哪些新的研究方向或可能性？
- 跨领域的借鉴价值和应用前景如何？

### 第5个Why：长远意义（Why 5 - Long-term Significance）
**问题：这个创新的长远意义是什么？**
- 该创新在未来5-10年可能产生什么影响？
- 可能催生什么样的后续工作或技术演进？
- 对整个学科或相关产业的发展方向有何指引？
- 是否具有成为经典方法或开创性工作的潜力？

## 输出格式

```markdown
# 深度研究

## 核心创新点
[1-2句话清晰界定论文的核心创新是什么]

## 第1层追问：根本问题
### 为什么需要这个创新？
[回答根本问题的4个方面]

## 第2层追问：技术机制
### 核心技术原理是什么？
[回答技术机制的4个方面]

## 第3层追问：有效性来源
### 为什么这个创新是有效的？
[回答有效性的4个方面]

## 第4层追问：深层价值
### 这个创新的深层价值是什么？
[回答深层价值的4个方面]

## 第5层追问：长远意义
### 这个创新的长远意义是什么？
[回答长远意义的4个方面]
```

要求：
- 每一层的追问都要深入到本质，避免表面化描述
- 技术术语使用英文原文（首次出现时加中文注释）
- 逻辑递进，层层深入，形成完整的分析链条
- 每层回答控制在150-200字，总计800-1000字
- 分析要有深度，展现对论文创新本质的深刻理解"""

    @staticmethod
    def _tldr_prompt() -> str:
        return """你是一位专业的科研论文分析师。请将前面的内容摘要和深度研究整合成一段简洁的TLDR（Too Long; Didn't Read）总结，并使用中文输出：

## 分析要求

TLDR（"太长不看"）是一种单段式快速总结，让读者在30秒内掌握论文的核心信息。请整合"内容摘要"和"深度研究"的精华，形成一段精炼的总结。

### 内容结构
1. **研究主题**（1句话）：这篇论文研究什么问题？
2. **核心创新**（1-2句话）：提出了什么新方法/新发现？
3. **主要结果**（1句话）：取得了什么关键成果？
4. **价值意义**（1句话）：为什么重要？有什么影响？

### 写作原则
- 开门见山，直接点明核心
- 每句话都有实质性内容，避免冗余
- 突出创新点和贡献，而非背景信息
- 使用简洁有力的学术表述
- 技术术语保留英文原文（关键术语可加括号注释）

## 输出格式

```
本文[研究主题]，提出了[核心创新]。实验/理论表明，[主要结果]。该工作[价值意义]。
```

示例：
```
本文研究大语言模型在长文本理解上的局限性，提出了FlashAttention算法来实现高效注意力机制。实验表明，该方法在保持模型性能的同时将训练速度提升了2-3倍，内存使用减少了一半。该工作为长序列建模提供了新的技术范式，已被广泛应用于GPT-4等大模型的训练中。
```

要求：
- 严格控制在3-5句话，100-150字
- 一段式输出，不分段
- 信息密度高，每句话都有价值
- 避免使用"本文提出..."等重复表达，自然流畅"""


@dataclass
class SummaryResult:
    """
    Result of a summarization step.

    Contains the generated summary and metadata about the step.

    Attributes:
        step: The summary step that was performed.
        content: Generated summary text.
        success: Whether the step completed successfully.
        error_message: Error message if the step failed.
    """

    step: SummaryStep
    content: str
    success: bool = True
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert result to dictionary."""
        return {
            "step": self.step.value,
            "step_name": self.step.display_name,
            "content": self.content,
            "success": self.success,
            "error_message": self.error_message,
        }


class PaperSummarizer:
    """
    Orchestrates multi-step paper summarization using LLM.

    The summarizer executes configured workflow steps to extract
    different types of information from a paper. Steps can be
    executed individually or as a complete workflow.

    Typical usage:
        >>> config = Config.from_env()
        >>> summarizer = PaperSummarizer(config)
        >>> results = summarizer.summarize_paper(paper_id=1)
        >>> for result in results:
        ...     print(f"{result.step.display_name}: {result.content[:100]}...")

    Attributes:
        llm_client: LLM client for generating summaries.
        pdf_parser: PDF parser for text extraction.
        max_input_length: Maximum characters of paper text to send to LLM.
    """

    DEFAULT_MAX_INPUT_LENGTH = 15000  # Characters, not tokens

    def __init__(
        self,
        config: Optional[Config] = None,
        llm_client: Optional[LLMClient] = None,
        pdf_parser: Optional[PDFParser] = None,
        max_input_length: int = DEFAULT_MAX_INPUT_LENGTH,
    ):
        """
        Initialize the paper summarizer.

        Args:
            config: Application configuration.
            llm_client: Pre-configured LLM client. If None, creates from config.
            pdf_parser: Pre-configured PDF parser. If None, creates from config.
            max_input_length: Maximum characters of paper text to include in LLM input.
        """
        self.config = config or Config.from_env()
        self.llm_client = llm_client or LLMClient(self.config.llm)
        self.pdf_parser = pdf_parser or PDFParser(self.config.ocr)
        self.max_input_length = max_input_length

    def _prepare_paper_text(
        self,
        title: str,
        abstract: str,
        full_text: Optional[str] = None,
    ) -> str:
        """
        Prepare paper text for LLM input.

        Combines title, abstract, and selected portions of full text
        while staying within the max input length limit.

        Args:
            title: Paper title.
            abstract: Paper abstract.
            full_text: Full paper text (optional).

        Returns:
            Prepared text string for LLM input.
        """
        # Start with title and abstract
        parts = [
            f"Title: {title}",
            f"Abstract: {abstract}",
        ]

        # Add full text if available (truncated to fit limit)
        if full_text:
            # Reserve space for title and abstract
            reserved = sum(len(p) for p in parts) + 100
            available = self.max_input_length - reserved

            if available > 500:  # Only include if we have reasonable space
                truncated = full_text[:available]
                parts.append(f"Paper Content (excerpt):\n{truncated}")

        return "\n\n".join(parts)

    def _run_step(
        self,
        step: SummaryStep,
        paper_text: str,
    ) -> SummaryResult:
        """
        Execute a single summarization step.

        Args:
            step: The summary step to execute.
            paper_text: Prepared paper text.

        Returns:
            SummaryResult with generated content.
        """
        try:
            system_prompt = step.prompt
            user_prompt = f"""请分析以下研究论文并提供{step.display_name}部分的总结：

{paper_text}

请严格按照上述提示词要求的格式和指南进行输出，确保：
1. 使用专业的学术中文表述
2. 技术术语保留英文原文（首次出现时加括号注释）
3. 结构清晰，层次分明
4. 内容精简，重点突出
"""

            content = self.llm_client.chat_with_system(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.3,  # Lower temperature for more focused summaries
            )

            return SummaryResult(step=step, content=content, success=True)

        except Exception as e:
            logger.error(f"Step {step.value} failed: {e}")
            return SummaryResult(
                step=step,
                content="",
                success=False,
                error_message=str(e),
            )

    def summarize_paper(
        self,
        paper: Paper,
        steps: Optional[List[SummaryStep]] = None,
        save_to_db: bool = True,
    ) -> List[SummaryResult]:
        """
        Run the summarization workflow for a paper.

        Executes the specified steps. If not specified, uses the new 3-step workflow:
        CONTENT_SUMMARY, DEEP_RESEARCH, TLDR.

        Args:
            paper: Paper record to summarize.
            steps: List of steps to execute. If None, runs new 3-step workflow.
            save_to_db: Whether to save results to database.

        Returns:
            List of SummaryResult objects, one per step.
        """
        logger.info(f"Starting summarization for paper {paper.id}: {paper.title[:50]}...")

        # Validation 1: Title must exist
        if not paper.title or paper.title.strip() == "":
            logger.warning(f"Paper {paper.id} has no title, skipping summarization")
            return []

        # Validation 2: At least need title or abstract
        if not paper.abstract:
            logger.warning(
                f"Paper {paper.id} ('{paper.title[:50]}...') has no abstract"
            )

        # Validation 3: Need PDF or text file
        if not paper.pdf_path and not paper.text_path:
            logger.error(f"Paper {paper.id} has no PDF or text file")
            return []

        # Parse PDF if needed
        if paper.text_path:
            logger.debug(f"Using existing text file: {paper.text_path}")
            full_text = Path(paper.text_path).read_text(encoding="utf-8")
        elif paper.pdf_path:
            logger.debug(f"Parsing PDF file: {paper.pdf_path}")
            parse_result = self.pdf_parser.parse(paper)
            if not parse_result.success:
                logger.error(f"Failed to parse PDF for paper {paper.id}")
                return []
            full_text = parse_result.text
            # Parser now automatically sets paper.text_path
        else:
            full_text = None

        # Validation 4: Check text quality
        if full_text and len(full_text.strip()) < 100:
            logger.warning(
                f"Paper {paper.id} extracted text too short ({len(full_text)} chars)"
            )

        # Prepare text for LLM
        paper_text = self._prepare_paper_text(
            title=paper.title,
            abstract=paper.abstract or "",
            full_text=full_text,
        )

        # Validation 5: Check prepared text length
        if len(paper_text.strip()) < 50:
            logger.warning(
                f"Paper {paper.id} prepared text too short ({len(paper_text)} chars), skipping"
            )
            return []

        logger.debug(f"Prepared text length: {len(paper_text)} chars")

        # Use new 3-step workflow by default
        if steps is None:
            steps = [
                SummaryStep.CONTENT_SUMMARY,
                SummaryStep.DEEP_RESEARCH,
                SummaryStep.TLDR
            ]
            logger.info(f"Running 3-step summarization workflow: {[s.value for s in steps]}")

        # Run specified steps
        steps_to_run = steps
        results: List[SummaryResult] = []

        for step in steps_to_run:
            logger.info(f"Running step: {step.display_name} for paper {paper.id}")
            result = self._run_step(step, paper_text)
            results.append(result)

            if result.success:
                logger.info(
                    f"Step {step.display_name} completed: {len(result.content)} chars"
                )
            else:
                logger.warning(
                    f"Step {step.display_name} failed: {result.error_message}"
                )

            # Save to database if requested and successful
            if save_to_db and result.success:
                from daily_paper.database import Summary

                # Check for existing summary of this type
                existing = (
                    self._get_db_session()
                    .query(Summary)
                    .filter_by(paper_id=paper.id, summary_type=step.value)
                    .first()
                )

                if existing:
                    existing.content = result.content
                else:
                    new_summary = Summary(
                        paper_id=paper.id,
                        summary_type=step.value,
                        content=result.content,
                    )
                    self._get_db_session().add(new_summary)

                self._get_db_session().commit()

        return results

    def _get_db_session(self) -> Session:
        """Get or create database session."""
        if not hasattr(self, "_db_session"):
            from daily_paper.database import init_db

            self._db_session = init_db(self.config.database.url)
        return self._db_session

    def close(self) -> None:
        """Close database session and clean up resources."""
        if hasattr(self, "_db_session"):
            self._db_session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.close()
