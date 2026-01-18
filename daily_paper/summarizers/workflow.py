"""
Multi-step paper summarization workflow using LLM.

This module implements an orchestratable workflow for summarizing research
papers. Each step extracts specific information using dedicated prompts.

The workflow consists of multiple steps:
1. Basic Info - authors, affiliations, domain
2. Background - research context and motivation
3. Core Contributions - main innovations
4. Problem Statement - what problem is being solved
5. Technical Methods - algorithms and techniques
6. Experimental Results - key data points
7. Conclusions - findings and implications
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

    Values:
        BASIC_INFO: Author information, affiliations, research domain
        BACKGROUND: Research background and motivation
        CONTRIBUTIONS: Core innovations and contributions
        PROBLEM: Problem being addressed
        METHODS: Technical methods and algorithms
        RESULTS: Experimental results and data
        CONCLUSIONS: Conclusions and implications
    """

    BASIC_INFO = "basic_info"
    BACKGROUND = "background"
    CONTRIBUTIONS = "contributions"
    PROBLEM = "problem"
    METHODS = "methods"
    RESULTS = "results"
    CONCLUSIONS = "conclusions"

    @property
    def display_name(self) -> str:
        """Human-readable display name for the step."""
        names = {
            self.BASIC_INFO: "基本信息",
            self.BACKGROUND: "研究背景",
            self.CONTRIBUTIONS: "核心贡献",
            self.PROBLEM: "问题陈述",
            self.METHODS: "技术方法",
            self.RESULTS: "实验结果",
            self.CONCLUSIONS: "结论与启示",
        }
        return names.get(self, self.value)

    @property
    def prompt(self) -> str:
        """Get the system prompt for this summarization step."""
        prompts = {
            self.BASIC_INFO: self._basic_info_prompt(),
            self.BACKGROUND: self._background_prompt(),
            self.CONTRIBUTIONS: self._contributions_prompt(),
            self.PROBLEM: self._problem_prompt(),
            self.METHODS: self._methods_prompt(),
            self.RESULTS: self._results_prompt(),
            self.CONCLUSIONS: self._conclusions_prompt(),
        }
        return prompts.get(self, "")

    @staticmethod
    def _basic_info_prompt() -> str:
        return """你是一位专业的科研论文分析师。请从论文中提取以下基本信息，并使用中文输出：

## 分析要求

请提取并整理以下信息，使用专业、精简的中文表述：

### 1. 作者与机构
- 第一作者及其他核心作者姓名
- 作者所属机构/大学
- 通讯作者（如有标注）

### 2. 研究领域
- 一级学科（如：计算机科学、物理学、数学）
- 二级领域（如：计算机视觉、自然语言处理、深度学习）
- 研究方向关键词（3-5个）

### 3. 发表信息
- 发表会议/期刊（如已发表）
- arXiv编号及提交日期
- 论文类型（综述/研究论文/短文等）

## 输出格式

请使用以下结构化格式输出（Markdown）：

```markdown
# 基本信息

## 作者与机构
- **作者**: [作者列表]
- **机构**: [机构名称]

## 研究领域
- **一级领域**: [领域名称]
- **二级领域**: [具体方向]
- **关键词**: [关键词1, 关键词2, ...]

## 发表信息
- **来源**: [会议/期刊/arXiv]
- **编号**: [论文ID]
- **日期**: [发表日期]
```

要求：
- 专业术语保留英文原文，首次出现时加括号注释
- 机构名称使用中文官方译名或保留英文
- 信息完整、准确、精简"""

    @staticmethod
    def _background_prompt() -> str:
        return """你是一位专业的科研论文分析师。请分析论文的研究背景与动机，并使用中文输出：

## 分析视角

从以下维度系统性地分析研究背景：

### 1. 领域定位
- 该研究属于哪个大的研究方向？
- 当前该领域的发展趋势如何？
- 该方向在学术界/工业界的重要性

### 2. 研究动机
- 为什么需要做这项研究？（实际需求/理论缺口）
- 现状存在什么核心问题？
- 解决这个问题有什么价值？

### 3. 知识缺口
- 现有研究在哪些方面存在不足？
- 本文要填补的具体gap是什么？
- 为什么这个gap重要且有挑战性？

### 4. 相关工作
- 引用了哪些最相关的前沿工作？
- 本文与这些工作的关系是什么？
- 在现有研究基础上的推进点

## 输出格式

```markdown
# 研究背景

## 领域定位
[1-2句话描述研究领域的定位和重要性]

## 研究动机
[清晰阐述为什么需要这项研究]

## 核心问题与知识缺口
- **现有局限**: [当前方法的不足]
- **研究gap**: [本文要填补的具体空白]
- **挑战性**: [为什么这个问题有难度]

## 相关工作
[简要介绍最相关的2-3项前沿工作及其与本文的关系]
```

要求：
- 使用专业的学术中文表述
- 技术术语保留英文原文（首次出现加注释）
- 逻辑清晰，层次分明，控制在300-500字"""

    @staticmethod
    def _contributions_prompt() -> str:
        return """你是一位专业的科研论文分析师。请分析论文的核心创新点，并使用中文输出：

## 分析要求

从以下维度系统性地提炼核心贡献：

### 1. 主要创新
- 提出了什么新方法/新模型/新理论？
- 与现有方法相比，本质区别在哪里？
- 创新点的技术亮点是什么？

### 2. 理论贡献
- 在理论层面有什么突破？
- 是否提出了新的问题定义/框架/范式？
- 理论分析或证明的核心要点

### 3. 实践贡献
- 解决了什么实际问题？
- 性能提升的具体表现（如果已知）
- 开源了什么资源（数据集/代码/模型）

### 4. 影响力
- 该工作对领域的影响如何？
- 可能的后续研究方向启发

## 输出格式

```markdown
# 核心贡献

## 主要创新点
[清晰列出本文的1-3个核心创新，每个创新说明具体是什么]

## 理论贡献
[如果有理论突破，说明理论层面贡献；否则说明设计理念的创新性]

## 实践贡献
- **问题解决**: [解决了什么具体问题]
- **性能提升**: [相比baseline的提升，如果实验部分已完成]
- **资源贡献**: [开源的数据集/代码/模型等]

## 技术亮点
[用2-3句话概括最亮的技术特色]
```

要求：
- 突出"创新性"和"贡献度"
- 使用专业术语但表述清晰
- 控制在300-400字"""

    @staticmethod
    def _problem_prompt() -> str:
        return """你是一位专业的科研论文分析师。请分析论文要解决的核心问题，并使用中文输出：

## 分析要求

### 1. 问题定义
- 本文要解决的具体问题是什么？
- 问题的形式化定义（如果论文给出）
- 问题的输入和输出是什么？

### 2. 问题重要性
- 这个问题为什么重要？
- 有什么实际应用场景或理论价值？
- 不解决这个问题会有什么后果？

### 3. 技术挑战
- 该问题的难点在哪里？
- 为什么现有方法无法很好地解决？
- 需要克服哪些技术障碍？

### 4. 问题边界
- 问题的适用范围和限制条件
- 什么样的场景下这个问题不适用
- 与其他相关问题的区别

## 输出格式

```markdown
# 问题陈述

## 核心问题
[清晰定义本文要解决的具体问题]

## 问题重要性
[说明为什么这个问题值得研究]

## 技术挑战
- **挑战1**: [具体难点]
- **挑战2**: [具体难点]
- **挑战3**: [具体难点]

## 现有方法的局限
[现有方法为什么无法有效解决此问题]
```

要求：
- 问题定义要精确、具体
- 说明清楚"为什么难"
- 控制在200-300字"""

    @staticmethod
    def _methods_prompt() -> str:
        return """你是一位专业的科研论文分析师。请分析论文的技术方法，并使用中文输出：

## 分析要求

### 1. 整体框架
- 方法论的整体思路是什么？
- 采用了什么技术架构或范式？
- 方法的流程步骤是什么？

### 2. 核心技术
- 使用了哪些关键技术或算法？
- 关键模块的设计思想
- 模型/算法的核心创新点

### 3. 技术细节
- 重要的技术组件
- 损失函数或优化目标（如有）
- 训练策略或推理过程

### 4. 方法论特点
- 方法的主要优势
- 相比现有方法的技术差异
- 计算复杂度或效率考虑

## 输出格式

```markdown
# 技术方法

## 整体框架
[概述方法论的总体思路和技术架构]

## 核心技术
### 技术组件1：[名称]
- **功能**: [该组件的作用]
- **创新点**: [设计特色]

### 技术组件2：[名称]
- **功能**: [该组件的作用]
- **创新点**: [设计特色]

## 方法流程
[用简洁的语言描述方法的主要步骤]

## 技术优势
[相比现有方法的技术优势和特点]
```

要求：
- 技术术语使用英文原文
- 重点突出"如何做"而非泛泛而谈
- 配合公式或伪代码描述更佳（如果论文中有）
- 控制在400-600字"""

    @staticmethod
    def _results_prompt() -> str:
        return """你是一位专业的科研论文分析师。请分析论文的实验结果，并使用中文输出：

## 分析要求

### 1. 实验设置
- 使用了哪些数据集？
- 评估指标是什么？
- 对比了哪些baseline方法？

### 2. 主要结果
- 核心实验的关键数据
- 定量结果的具体数值
- 与baseline的性能对比

### 3. 消融实验
- 关键模块的贡献分析
- 设计选择的有效性验证

### 4. 结果分析
- 为什么能取得这样的结果？
- 方法的哪些特性带来了性能提升
- 结果的含义和启示

## 输出格式

```markdown
# 实验结果

## 实验设置
- **数据集**: [使用的数据集]
- **评估指标**: [具体的评估指标]
- **对比方法**: [baseline方法列表]

## 主要结果
### [任务1]结果
| 方法 | 指标1 | 指标2 | 指标3 |
|------|-------|-------|-------|
| Baseline1 | XX.X | XX.X | XX.X |
| Baseline2 | XX.X | XX.X | XX.X |
| **本文方法** | **XX.X** | **XX.X** | **XX.X** |

### [任务2]结果
[类似格式]

## 消融实验
[关键组件的消融分析结果]

## 结果分析
[解释为什么本文方法有效，哪些设计带来了提升]
```

要求：
- 准确提取关键数值结果
- 使用表格呈现对比数据
- 说明结果的意义
- 控制在300-500字"""

    @staticmethod
    def _conclusions_prompt() -> str:
        return """你是一位专业的科研论文分析师。请总结论文的结论与启示，并使用中文输出：

## 分析要求

### 1. 核心结论
- 本文的主要发现是什么？
- 回答了什么研究问题？
- 验证了什么假设？

### 2. 研究意义
- 对领域有什么贡献？
- 可能的实际应用价值
- 对后续研究的启发

### 3. 局限性
- 作者承认了哪些不足？
- 方法有什么适用范围限制？
- 还有哪些未解决的问题？

### 4. 未来工作
- 作者建议了哪些研究方向？
- 该领域可能的发展趋势

## 输出格式

```markdown
# 结论与启示

## 核心结论
[2-3句话总结论文的核心发现和贡献]

## 研究意义
- **学术价值**: [对领域的理论贡献]
- **应用价值**: [实际应用的潜力]
- **方法启示**: [对后续研究的方法论启发]

## 局限性
- **方法局限**: [适用范围和限制条件]
- **待解决问题**: [尚未解决的问题]

## 未来方向
[作者建议的或可预见的后续研究方向]
```

要求：
- 结论要与贡献部分呼应但不重复
- 客观评价局限性
- 展望要有前瞻性
- 控制在200-300字"""


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

        Executes the specified steps (or all steps if not specified)
        and optionally saves results to the database.

        Args:
            paper: Paper record to summarize.
            steps: List of steps to execute. If None, runs all steps.
            save_to_db: Whether to save results to database.

        Returns:
            List of SummaryResult objects, one per step.
        """
        if not paper.pdf_path and not paper.text_path:
            logger.error(f"Paper {paper.id} has no PDF or text file")
            return []

        # Parse PDF if needed
        if paper.text_path:
            full_text = Path(paper.text_path).read_text(encoding="utf-8")
        elif paper.pdf_path:
            parse_result = self.pdf_parser.parse(paper.pdf_path)
            if not parse_result.success:
                logger.error(f"Failed to parse PDF for paper {paper.id}")
                return []
            full_text = parse_result.text
        else:
            full_text = None

        # Prepare text for LLM
        paper_text = self._prepare_paper_text(
            title=paper.title,
            abstract=paper.abstract or "",
            full_text=full_text,
        )

        # Run specified steps (or all steps)
        steps_to_run = steps or list(SummaryStep)
        results: List[SummaryResult] = []

        for step in steps_to_run:
            result = self._run_step(step, paper_text)
            results.append(result)

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
