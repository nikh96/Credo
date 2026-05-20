# Credo – Personal Finance Web App

#### Video Demo:  
<https://youtu.be/7BG6dLfZgKE>

#### Description:
Credo is a personal finance web application that helps users track income and expenses, organize transactions into categories, set budgets, and see simple reports about where their money goes over time. The goal of Credo is to act like a small “digital safe” for everyday people: a place where they can see where their money is going and make better decisions without needing complex spreadsheets or banking integrations.

---

## Features

Credo provides a complete, end‑to‑end flow for a single user to manage their own finances.

- **User accounts and authentication**  
  Users can register, log in, and log out securely. Passwords are stored in hashed form using standard library support rather than plain text. Sessions are handled by Flask so that each user’s data remains private to their account.

- **Transactions (income and expenses)**  
  Users can add transactions as either income or expense, specifying details such as amount, date, description, and category. Existing transactions can be edited or deleted. A main Transactions page lists records in a table so users can scroll through their history.

- **Categories and budgets**  
  Users can create their own custom categories (for example: Food, Rent, Transport, Recharges, Fees) instead of being limited to hard‑coded ones. On the Budgets page, users can set a monthly budget per category and see for each one: the budget amount, how much has been used this month based on transactions, and how much remains (or how far they are over budget).

- **Reports and summaries**  
  A Reports page provides an overview of spending and income over time. It includes monthly summaries and basic charts that visualize where money is going. Simple insights like total income, total expenses, and breakdown by category help the user understand their habits.

- **Data export**  
  Credo includes export features (such as CSV and/or JSON) so that users can download their transaction data for backup or for analysis in other tools.

- **Password reset and error pages**  
  A password reset flow allows a user who has forgotten their password to request a token‑based reset link. The app also provides custom 404 and 500 error pages in the same visual style as the rest of the site to give a more polished experience.

- **Informational pages**  
  The app includes static pages such as About, Help, Privacy, and Terms. These pages explain what Credo is, what data it stores, and set expectations that it is an educational personal finance tool and not a bank or financial adviser.

---

## Technologies

Credo is built with technologies covered in CS50 and commonly used in real‑world web development:

- **Backend:** Python and Flask for routing, business logic, authentication, and templates.
- **Database:** SQLite accessed via an ORM layer (such as SQLAlchemy) or direct SQL queries for persistent storage of users, transactions, categories, and budgets.
- **Frontend:** HTML templates using Jinja, CSS for layout and theming, and a small amount of JavaScript for interactivity such as charts and modals.
- **Other tools:** The project is designed to run in a virtual environment and can be executed locally with the Flask development server.

---

## Project Structure

The main files and folders in Credo are:

1. `app.py` - is the main Flask application file that ties the whole project together. It defines the
routes for pages like dashboard, transactions, budgets, and reports, and wires them to the
underlying database models. It also condigures the app(secret key, database connection,
debug flags) and registers error handlers and any helper functions used across views/

2. `templates/ and base.html` - The templates/ folder contains all Jinja HTML templates that define the visual structure of Credo. These files are rendered by Flask and filled with dynamic data from the database.
base.html is the core layout template that includes the header, navigation bar, flash messages,
and footer. All other pages extend this file so that the app has a consistent look and feel 
with one place to change the global UI elements.


3. `dashboard.html` - dashboard.html shows the main overview a user sees after logging in. It typically contains
high-level summaries such as current balance, total income, and expenses, and quick links to
important actions like adding Transaction. This page is meant to answer "How am I doing this month?" at a glance.

`Transactions/ templates` - The transactions/ subfolder holds templates for viewing, creating, and editing income and expense records. One template renders a table of existing transactions with options to edit or
delete each entry. while others provide forms for adding or updating a transaction. Together
they implement the core CRUD interface that users rely on most frequently.

`budgets/ templates` - The budgets/ subfolder contains templates that render the Budgets page and any related
forms. These templates display budget rows per category with columns such as "Budget",
"Used this month", and "Remaining / Over". They also include forms that allow the user to set
or adjust budgets, turning a static page into a useful planning tool.

`reports/ templates` - The reports/ subfolder holds templates for Credo's reporting views. These pages show
aggregated information such as total income and expenses over a time period, as well as
breakdowns by category. They must also embed charts or summary cards that help users
visually understand spending patterns and trends over time.

`auth/ templates` - The auth/ subfolder includes templates for registration, login, and password reset flows.
These pages handle user-facing forms for creating an account, signing in, and requesting or
applying a password reset token. They are designed to integrate with Flask's session logic
while keeping the UI simple and understandable for first-time users.

`errors/ templates` - The errors/ subfolder contains custom templates for HTTP error pages such as 404 (Not Found) and 500 (Internal Server Error.) Instead of showing a default browser or framework
error, these templates present a friendly message in Credo's dark theme. This makes the app
feel more polished and gives users clearer guidance when something goes wrong.

`static_pages/ templates` - the static_pages/ subfolder stores templates for informational pages like About, Help, Privacy, and Terms. These pages explain what Credo is, how to use the app, what data is
stored, and any limitations or disclaimers. They don't change often, but they are important for
building trust and helping new users understand the context of the project.

`static/css/` - The static/css/ folder contains the stylesheets that control Credo's colors, typography,
spacing, and responsive behaviour. These CSS files define the dark theme, the layout of cards
and tables, and how elements rearrange on smaller screens. Changing these files allows you to
refine the visual identity of the app without touching the Python code.

`static/js/` - THe static/js/ folder holds JavaScript files that add small interactive behaviours to the
interface. This might include chart initialization, toggling of modals (such as an on-screen calculator),
or dynamic form enhancements. The JavaScript is kept light so that the app remains easy to understand while still feeling responsive.

`static/img/` - The static/img/ folder is where images used by the site are stored, such as the Credo logo
and any icons or illustrations. These assets are referenced by the templates to display
branding and visual cues. Keeping them in a dedicated folder makes it easier to manage and
replace images later if the design evolves.

`run.py` - is a small entry-point used to start the Credo application. Instead of running
Flask directly with environment variables, you can execute this file (for example with python run.py)
to launch the app using a predefined configuration. It typically imports the Flask
application instance from the main module and calls the run method, making it a convenient way to start the server development or testing.

`README.md` - README.md is the main documentation file for the project. It explains what Credo is, how to
install and run it, what each important file or folder does, and the design decisions made along
the way. This file is also where the CS50 video demo link and acknowledgements are recoreded, making it the first place a reviewer or collaborator should read.

`requirements.txt` - requirements.txt lists all of the Python packages that Credo depends on, such as Flask,
 SQLAlchemy, and any other libraries used by the project. it allows anyone who clones the
 repository to quickly install the same dependencies with a single command like pip install "-r requirements.txt", ensuring a consistent environment.
 
 `venv/ (Virtual Environment Folder)` - venv/ is the local virtual environment directory created to isolate this project's Python packages from the rest of the system. It contains the Python interpreter and installed libraries
 used while developing and testing Credo. This folder is typically not submitted to version
 control, but it explains how the project was run during development.

` There is some more files like templates/transactions/ edit.html and add.html. These are not so important in the sense to describe as paragraph these files are self-explanatory`

---

## How to Run

To run Credo locally:

1. Clone this repository or download the project folder.
2. Create and activate a Python virtual environment.
3. Install required dependencies, for example with:
   - `pip install -r requirements.txt`
4. Set environment variables as needed, such as:
   - `FLASK_APP=app.py`
   - `FLASK_ENV=development` (for local testing)
   - `SECRET_KEY` for Flask sessions.
5. Initialize the database (for example, by running a small setup script or migration command that creates the tables).
6. Start the application with `flask run` or `python app.py`.
7. Open the provided URL in your browser, register a new account, and begin adding transactions.

---

## Design and Implementation Details

The database is organized around a few core entities. A `User` table stores account information and password hashes. A `Transaction` table records each income or expense with references to the owning user and to a category. A `Category` table stores user‑defined categories such as Food or Rent. A `Budget` table associates a category with a budget limit for a given user and possibly a specific month or period.

Authentication uses typical web patterns. Passwords are never stored in plain text; instead, a hashing function is applied on registration and when checking credentials at login. Flask sessions keep the user logged in between requests while ensuring that each user only sees their own data. The password reset flow uses tokens embedded in URLs to verify that the correct user is resetting their password.

For budgets, the app calculates “used” amounts by aggregating the sums of transactions per category in the relevant period and comparing that to the stored budget amount. Reports use similar aggregations but grouped by month or by category to create summaries and charts. Error handling is centralized with Flask error handlers, which render custom templates for 404 and 500 status codes.

The user interface uses a consistent dark theme with a responsive layout so that pages remain usable on laptops and smaller screens. Navigation links, buttons, and icons are kept simple and clear to reduce visual noise.

---

## Design Decisions and Future Work

Flask and SQLite were chosen because they are lightweight, easy to set up, and align with CS50’s focus on understanding core web and database concepts rather than heavy frameworks. The project favors clarity over complexity: the features implemented are those that most directly help a user understand their spending. Future improvements could include more advanced analytics, savings goals, reminder features, better mobile layout, and full production deployment with HTTPS and a custom domain.

AI tools were used as helpers for some code snippets and explanations during development, but all logic was understood, integrated, and tested manually. Any such usage is noted in code comments where appropriate, in accordance with CS50’s policy.
