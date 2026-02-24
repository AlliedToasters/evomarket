## ADDED Requirements

### Requirement: Streamlit app entry point
The system SHALL provide a Streamlit application at `visualization/app.py` that serves as the single entry point for the visualization dashboard, runnable via `streamlit run visualization/app.py`.

#### Scenario: App starts successfully with no panels
- **WHEN** the app is launched with no panels registered
- **THEN** the app SHALL render without errors and display a welcome page explaining that no panels are loaded

#### Scenario: App starts with panels registered
- **WHEN** one or more panels are registered
- **THEN** the app SHALL render sidebar navigation listing all registered panels by name

### Requirement: Episode selection via sidebar
The system SHALL provide a file/directory input in the sidebar for selecting an episode output directory. The directory MUST contain an `episode.sqlite` file.

#### Scenario: Valid episode directory selected
- **WHEN** the user provides a path to a directory containing `episode.sqlite`
- **THEN** the app SHALL load the episode and display the active panel content

#### Scenario: No episode selected
- **WHEN** no episode directory has been provided
- **THEN** the app SHALL display a prompt asking the user to select an episode directory

#### Scenario: Invalid episode path
- **WHEN** the user provides a path that does not contain `episode.sqlite`
- **THEN** the app SHALL display an error message indicating the path is invalid

### Requirement: Panel registration
The system SHALL provide a `register_panel(name: str, render_func: Callable)` function that panels call to register themselves with the app shell.

#### Scenario: Panel registers successfully
- **WHEN** a panel module calls `register_panel("My Panel", my_render_function)`
- **THEN** the panel SHALL appear in the sidebar navigation with the name "My Panel"

#### Scenario: Panel render function signature
- **WHEN** a registered panel is selected by the user
- **THEN** the app SHALL call the panel's render function passing the database path as an argument

### Requirement: Sidebar navigation
The system SHALL render a sidebar with a radio button group listing all registered panels. Selecting a panel SHALL render that panel's content in the main area.

#### Scenario: Single panel registered
- **WHEN** exactly one panel is registered
- **THEN** the sidebar SHALL show that panel selected and the main area SHALL render its content

#### Scenario: Multiple panels registered
- **WHEN** multiple panels are registered
- **THEN** the sidebar SHALL list all panels and the user can switch between them via radio buttons

### Requirement: Welcome page with zero panels
The system SHALL display a welcome page when no panels are registered. The welcome page SHALL include the app title and a message indicating panels can be added.

#### Scenario: Welcome page content
- **WHEN** the app loads with no registered panels and a valid episode selected
- **THEN** the main area SHALL display a welcome message and episode summary information (ticks executed, agents, etc.) loaded from `result.json` if available
