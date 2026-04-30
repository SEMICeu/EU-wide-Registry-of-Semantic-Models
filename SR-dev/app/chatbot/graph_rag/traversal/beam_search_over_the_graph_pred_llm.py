import os
from typing import List, Dict, Any
from dotenv import load_dotenv
from langchain_neo4j import Neo4jGraph
from langchain_core.messages import HumanMessage
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser

import config
from .beam_search_over_the_graph import BeamSearchOverGraph
from ..prompts import RELATIONSHIP_SELECTION_PROMPT


class RelationshipSelection(BaseModel):
    selected_relationships: List[str] = Field(description="List of selected relationship types")
    reasoning: str = Field(description="Brief reasoning for the selection")


class BeamSearchOverGraphWithLLM:
    def __init__(
        self,
        beam_width: int = 10,
        max_depth: int = 3,
        max_total_nodes: int = 100,
        remove_mentions_nodes: bool = True,
        model: str = "gpt-4o-mini",
    ):
        self.beam_width = beam_width
        self.max_depth = max_depth
        self.max_total_nodes = max_total_nodes
        self.remove_mentions_nodes = remove_mentions_nodes
        self.model = model
        self._setup_environment()
        self._initialize_neo4j_connection()
        self._initialize_llm()

    def _setup_environment(self) -> None:
        load_dotenv()
        required_vars = ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if not os.getenv("PWC_API_KEY") and not os.getenv("OPENAI_API_KEY"):
            missing_vars.append("PWC_API_KEY or OPENAI_API_KEY")
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

    def _initialize_neo4j_connection(self) -> None:
        self.graph = Neo4jGraph(
            url=os.getenv("NEO4J_URI"),
            username=os.getenv("NEO4J_USERNAME"),
            password=os.getenv("NEO4J_PASSWORD"),
            refresh_schema=False,
        )

    def _initialize_llm(self) -> None:
        self.llm = config.llm
        self.output_parser = PydanticOutputParser(pydantic_object=RelationshipSelection)
        self.prompt_template = PromptTemplate(
            template=RELATIONSHIP_SELECTION_PROMPT,
            input_variables=["user_query", "relationship_types"],
            partial_variables={"format_instructions": self.output_parser.get_format_instructions()},
        )

    def _get_all_relationship_types(self) -> List[str]:
        try:
            cypher_query = """
            MATCH ()-[r]->()
            RETURN DISTINCT type(r) as relationship_type
            ORDER BY relationship_type
            """
            result = self.graph.query(cypher_query)
            return [row["relationship_type"] for row in result]
        except Exception:
            return []

    def _select_relevant_relationships(self, user_query: str, relationship_types: List[str]) -> List[str]:
        if not relationship_types:
            return []
        try:
            formatted_types = "\n".join([f"- {rel_type}" for rel_type in relationship_types])
            prompt = self.prompt_template.format(user_query=user_query, relationship_types=formatted_types)
            messages = [HumanMessage(content=prompt)]
            response = self.llm.invoke(messages)
            parsed_response = self.output_parser.parse(response.content)
            selected_rels = parsed_response.selected_relationships
            if "MENTIONS" not in selected_rels:
                selected_rels.append("MENTIONS")
            return selected_rels
        except Exception:
            return []

    def traverse_graph(self, relevant_docs: List[Dict[str, Any]], user_query: str) -> List[Dict[str, Any]]:
        try:
            all_relationship_types = self._get_all_relationship_types()
            if not all_relationship_types:
                return []

            selected_relationships = self._select_relevant_relationships(user_query, all_relationship_types)
            beam_search_traversal = BeamSearchOverGraph(
                beam_width=self.beam_width,
                max_depth=self.max_depth,
                max_total_nodes=self.max_total_nodes,
                remove_mentions_nodes=self.remove_mentions_nodes,
                rel_type_filter=selected_relationships if selected_relationships else None,
            )
            return beam_search_traversal.traverse_graph(relevant_docs, user_query)
        except Exception:
            return []

    def get_traversal_statistics(self) -> Dict[str, Any]:
        return {
            "method": "beam_search_over_the_graph_pred_llm",
            "beam_width": self.beam_width,
            "max_depth": self.max_depth,
            "max_total_nodes": self.max_total_nodes,
            "remove_mentions_nodes": self.remove_mentions_nodes,
            "model": self.model,
        }

