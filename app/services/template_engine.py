import os
import logging
from typing import Dict, Any, Tuple, Set
from jinja2 import Environment, FileSystemLoader, Template, meta, TemplateSyntaxError, TemplateError as JinjaTemplateError
from app.exceptions import TemplateError

logger = logging.getLogger("email_service")


class TemplateEngine:
    """
    Template engine using Jinja2. Handles template rendering and strict variable validation.
    """

    def __init__(self, template_dir: str = "app/templates"):
        self.template_dir = template_dir
        # Ensure template dir exists
        os.makedirs(self.template_dir, exist_ok=True)
        self.env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=True
        )

    def validate_variables(self, template_source: str, context: Dict[str, Any], template_name: str = "raw_template") -> None:
        """
        Parses the Jinja2 template source code to find all undeclared variables
        and raises a TemplateError if any required variable is missing in the context.
        """
        try:
            parsed_content = self.env.parse(template_source)
            required_variables = meta.find_undeclared_variables(parsed_content)
        except TemplateSyntaxError as e:
            logger.error(f"Syntax error in template '{template_name}': {e}")
            raise TemplateError(f"Syntax error in template '{template_name}' on line {e.lineno}: {e.message}")

        # Check for missing variables
        missing_vars = [var for var in required_variables if var not in context]
        if missing_vars:
            logger.error(f"Missing required placeholders for template '{template_name}': {missing_vars}")
            raise TemplateError(
                f"Missing required template placeholders for '{template_name}': {', '.join(missing_vars)}"
            )

    def render_from_file(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Renders a Jinja2 HTML/text template file after validating the context.
        """
        try:
            # Load template source to perform validation before compiling
            template_source, _, _ = self.env.loader.get_source(self.env, template_name)
            self.validate_variables(template_source, context, template_name)

            template = self.env.get_template(template_name)
            return template.render(context)
        except FileNotFoundError:
            logger.error(f"Template file not found: {template_name} in {self.template_dir}")
            raise TemplateError(f"Template file '{template_name}' not found.")
        except JinjaTemplateError as e:
            logger.error(f"Error rendering template file '{template_name}': {e}")
            raise TemplateError(f"Error rendering template '{template_name}': {e}")

    def render_from_string(self, template_source: str, context: Dict[str, Any], template_name: str = "raw_template") -> str:
        """
        Renders a Jinja2 template string after validating the context.
        """
        try:
            self.validate_variables(template_source, context, template_name)
            template = self.env.from_string(template_source)
            return template.render(context)
        except JinjaTemplateError as e:
            logger.error(f"Error rendering string template '{template_name}': {e}")
            raise TemplateError(f"Error rendering template '{template_name}': {e}")

    def render_subject(self, subject_template: str, context: Dict[str, Any]) -> str:
        """
        Renders a dynamic subject line from a template string.
        """
        try:
            self.validate_variables(subject_template, context, "subject_template")
            template = self.env.from_string(subject_template)
            return template.render(context)
        except JinjaTemplateError as e:
            logger.error(f"Error rendering subject template: {e}")
            raise TemplateError(f"Error rendering subject template: {e}")
