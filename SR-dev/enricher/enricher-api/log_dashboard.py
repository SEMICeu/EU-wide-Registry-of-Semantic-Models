import streamlit as st
import json
from pathlib import Path
from datetime import datetime
import plotly.express as px
import time

st.set_page_config(layout="wide", page_title="Log Dashboard")

log_file = st.sidebar.file_uploader("Upload log file", type=["log", "json"])

# Sidebar options
if st.sidebar.button("🔄 Refresh Dashboard", use_container_width=True):
    st.rerun()

def load_logs(file) -> list:
    logs = []
    parse_errors = []
    
    try:
        # Reset file pointer to beginning
        file.seek(0)
        
        # Read content
        content = file.read()
        
        # If it's bytes, decode to string
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='replace')
        
        # Split into lines and process each
        lines = content.strip().split('\n')
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
                
            try:
                # Try to parse as JSON
                log_entry = json.loads(line)
                logs.append(log_entry)
            except json.JSONDecodeError as je:
                # Try to fix common escape sequence issues
                try:
                    # Method 1: Try to fix double backslashes
                    fixed_line = line.replace('\\\\', '\\')
                    log_entry = json.loads(fixed_line)
                    logs.append(log_entry)
                    continue
                except:
                    pass
                
                try:
                    # Method 2: Try raw string parsing (escape backslashes)
                    import re
                    # Fix unescaped backslashes that aren't part of valid escape sequences
                    fixed_line = re.sub(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', line)
                    log_entry = json.loads(fixed_line)
                    logs.append(log_entry)
                    continue
                except:
                    pass
                
                try:
                    # Method 3: Try using ast.literal_eval as a fallback for simple cases
                    import ast
                    log_entry = ast.literal_eval(line)
                    if isinstance(log_entry, dict):
                        logs.append(log_entry)
                        continue
                except:
                    pass
                
                # If all methods fail, record the error but don't spam the UI
                parse_errors.append(f"Line {i}: {str(je)[:100]}...")
                
                # Create a fallback entry for severely malformed lines
                logs.append({
                    "time": datetime.now().isoformat(),
                    "level": "PARSE_ERROR",
                    "name": "log_parser",
                    "message": f"Could not parse line {i}: {line[:200]}...",
                    "original_line": line
                })
                
            except Exception as e:
                parse_errors.append(f"Line {i}: Unexpected error - {str(e)[:100]}...")
                continue
        
        # Show summary of parse errors if any, but don't spam
        if parse_errors:
            error_count = len(parse_errors)
            if error_count <= 5:
                for error in parse_errors:
                    st.warning(error)
            else:
                st.warning(f"Found {error_count} parsing errors. First few:")
                for error in parse_errors[:3]:
                    st.warning(error)
                with st.expander(f"Show all {error_count} parsing errors"):
                    for error in parse_errors:
                        st.text(error)
                
        return logs
        
    except Exception as e:
        st.error(f"Error reading log file: {e}")
        return []

if log_file is not None:
    logs = load_logs(log_file)
    
    if logs:
        st.success(f"Successfully loaded {len(logs)} log entries")
        
        # Dynamic max_rows slider based on actual log count
        max_available = len(logs)
        default_rows = min(20, max_available)  # Default to 20 or max available if less
        max_rows = st.sidebar.slider(
            "Visible rows in table", 
            min_value=5, 
            max_value=max_available, 
            value=default_rows
        )
        
        # Normalize levels and names for filters
        names = sorted({log.get("name", "Unknown").strip() for log in logs if log.get("name")})
        levels = sorted({log.get("level", "Unknown").strip().upper() for log in logs if log.get("level")})

        # Sidebar filters
        selected_name = st.sidebar.selectbox("Filter by name", ["All"] + names)
        selected_level = st.sidebar.selectbox("Filter by level", ["All"] + levels)
        search_text = st.sidebar.text_input("Search logs")

        # Apply filters
        filtered_logs = logs
        if selected_name != "All":
            filtered_logs = [log for log in filtered_logs if log.get("name", "").strip() == selected_name]
        if selected_level != "All":
            filtered_logs = [log for log in filtered_logs if log.get("level", "").strip().upper() == selected_level]
        if search_text:
            filtered_logs = [log for log in filtered_logs if search_text.lower() in str(log.get("message", "")).lower()]

        # Show filter results
        if len(filtered_logs) != len(logs):
            st.info(f"Showing {len(filtered_logs)} of {len(logs)} log entries")

        # --- Layout ---
        col1, col2 = st.columns([3, 1])

        # Column 1: Log table
        with col1:
            st.subheader("Logs")
            if filtered_logs:
                table_logs = [
                    {
                        "Time": log.get("time", "N/A"),
                        "Level": log.get("level", "N/A"),
                        "Name": log.get("name", "N/A"),
                        "Message": str(log.get("message", "N/A"))[:200] + ("..." if len(str(log.get("message", ""))) > 200 else ""),
                    }
                    for log in filtered_logs[-max_rows:]  # Show most recent entries
                ]
                st.dataframe(table_logs, height=max_rows*35, use_container_width=True)
            else:
                st.info("No logs match the current filters")

        # Column 2: Charts
        with col2:
            st.subheader("Log Statistics")
            
            if filtered_logs:
                # Count by level
                level_counts = {}
                for log in filtered_logs:
                    lvl = log.get("level", "Unknown").strip().upper()
                    if lvl:  # Only count non-empty levels
                        level_counts[lvl] = level_counts.get(lvl, 0) + 1
                
                if level_counts:
                    fig_level = px.bar(
                        x=list(level_counts.keys()),
                        y=list(level_counts.values()),
                        labels={"x": "Level", "y": "Count"},
                        title="Logs by Level",
                        color=list(level_counts.keys()),
                    )
                    fig_level.update_layout(showlegend=False, height=300)
                    st.plotly_chart(fig_level, use_container_width=True)

                # Count by name
                name_counts = {}
                for log in filtered_logs:
                    nm = log.get("name", "Unknown").strip()
                    if nm:  # Only count non-empty names
                        name_counts[nm] = name_counts.get(nm, 0) + 1
                
                if name_counts and len(name_counts) <= 10:  # Only show if not too many names
                    fig_name = px.pie(
                        values=list(name_counts.values()),
                        names=list(name_counts.keys()),
                        title="Logs by Name",
                    )
                    fig_name.update_layout(height=300)
                    st.plotly_chart(fig_name, use_container_width=True)
                elif name_counts:
                    st.info(f"Too many unique names ({len(name_counts)}) to display chart")

                # Show some basic stats
                st.metric("Total Filtered Logs", len(filtered_logs))
                if level_counts:
                    most_common_level = max(level_counts, key=level_counts.get)
                    st.metric("Most Common Level", most_common_level, level_counts[most_common_level])
            else:
                st.info("No data to display")

        # Raw data expander for debugging
        with st.expander("Debug: Show raw log sample"):
            if logs:
                st.json(logs[0] if logs else {})
                st.text("Sample log keys: " + str(list(logs[0].keys()) if logs else "None"))
    else:
        st.warning("No valid log entries found in the uploaded file")

# Manual refresh button at the bottom for convenience
if st.button("🔄 Refresh", help="Refresh the dashboard"):
    st.rerun()