from datetime import datetime, timedelta
from flask import Flask, request, render_template, session, url_for, redirect, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import secrets

app = Flask(__name__)

# SQLAlchemy Setup
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:Hemaramachandran6010@localhost/dummy'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = secrets.token_hex(16)
db = SQLAlchemy(app)


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        sql = text("SELECT * FROM user WHERE username = :username")
        user = db.session.execute(sql, {"username": username}).fetchone()

        if user and user._mapping['user_password'] == password:  # Check password
            session['user_id'] = user._mapping['User_id']
            session['family_head_id'] = user._mapping['family_head_id']
            return redirect(url_for('savings_goals'))
        else:
            flash('Invalid credentials')
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/savings_goals', methods=['GET', 'POST'])
def savings_goals():
    user_id = session.get('user_id')
    family_head_id = session.get('family_head_id')

    if not user_id or not family_head_id:
        flash("User not logged in or family information unavailable.")
        return redirect(url_for('login'))

    # Update expired goals
    sql_update = text("""
        UPDATE Savings_goals
        SET Goal_status = 'Not Achieved'
        WHERE End_date < CURRENT_DATE
          AND Goal_status NOT IN ('Achieved', 'Cancelled');
    """)
    db.session.execute(sql_update)
    db.session.commit()

    # Filters and search
    status_filter = request.args.get('status', 'all')
    search_query = request.form.get('search_query', '').strip()

    # Build query dynamically
    base_query = """
        SELECT * 
        FROM Savings_goals
        WHERE 
            ((Goal_type = 'Personal' AND User_id = :user_id)
            OR
            (Goal_type = 'Family' AND Family_head_id = :family_head_id))
    """

    if status_filter != 'all':
        base_query += " AND Goal_status = :status_filter"

    if search_query:
        base_query += " AND Goal_description LIKE :search_query"

    sql = text(base_query)

    query_params = {
        "user_id": user_id,
        "family_head_id": family_head_id,
        "status_filter": status_filter if status_filter != 'all' else None,
        "search_query": f"%{search_query}%" if search_query else None
    }

    savings_goals = db.session.execute(sql, {k: v for k, v in query_params.items() if v is not None}).fetchall()

    return render_template(
        "home.html",
        datas=savings_goals,
        status_filter=status_filter,
        search_query=search_query
    )


@app.route("/add_amount/<string:id>", methods=["GET", "POST"])
def add_amount(id):
    user_id = session.get("user_id")
    family_head_id = session.get("family_head_id")

    sql = text("""
        SELECT * FROM Savings_goals 
        WHERE Goal_id = :goal_id AND (User_id = :user_id OR family_head_id = :family_head_id)
    """)
    goal = db.session.execute(sql, {"goal_id": id, "user_id": user_id, "family_head_id": family_head_id}).fetchone()

    if not goal:
        flash("Goal not found")
        return redirect(url_for("savings_goals"))

    if request.method == "POST":
        additional_amount = float(request.form["additional_amount"])

        # Update achieved_amount
        update_sql = text("""
            UPDATE Savings_goals 
            SET Achieved_amount = COALESCE(Achieved_amount, 0) + :amount
            WHERE Goal_id = :goal_id AND (User_id = :user_id OR family_head_id = :family_head_id)
        """)
        db.session.execute(update_sql, {
            "amount": additional_amount,
            "goal_id": id,
            "user_id": user_id,
            "family_head_id": family_head_id
        })

        # Update goal status
        goal = db.session.execute(sql, {"goal_id": id, "user_id": user_id, "family_head_id": family_head_id}).fetchone()
        achieved_amount = goal._mapping["Achieved_amount"]
        target_amount = goal._mapping["Target_amount"]

        status = "Achieved" if achieved_amount >= target_amount else "Active"
        status_sql = text("""
            UPDATE Savings_goals 
            SET Goal_status = :status
            WHERE Goal_id = :goal_id AND (User_id = :user_id OR family_head_id = :family_head_id)
        """)
        db.session.execute(status_sql, {"status": status, "goal_id": id, "user_id": user_id, "family_head_id": family_head_id})
        db.session.commit()

        flash("Amount Added Successfully!")
        return redirect(url_for("savings_goals"))

    return render_template("add_amount.html", data=goal)


@app.route("/addgoal", methods=['GET', 'POST'])
def add_Goal():
    family_head_id = session.get('family_head_id')
    user_id = session.get('user_id')

    if request.method == "POST":
        target_amount = request.form['target_amount']
        start_date_str = request.form['start_date']
        end_date_str = request.form['end_date']
        goal_description = request.form['goal_description']
        goal_type = request.form['goal_type']

        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

        today = datetime.now().date()
        goal_status = "Not Achieved" if today > end_date.date() else "Active"

        sql = text("""
            INSERT INTO Savings_goals 
            (User_id, family_head_id, Target_amount, start_date, end_date, Goal_description, Goal_type, Goal_status)
            VALUES (:user_id, :family_head_id, :target_amount, :start_date, :end_date, :goal_description, :goal_type, :goal_status)
        """)
        db.session.execute(sql, {
            "user_id": user_id,
            "family_head_id": family_head_id,
            "target_amount": target_amount,
            "start_date": start_date,
            "end_date": end_date,
            "goal_description": goal_description,
            "goal_type": goal_type,
            "goal_status": goal_status
        })
        db.session.commit()

        flash("Goal Added Successfully")
        return redirect(url_for('savings_goals'))

    return render_template("addgoals.html")


@app.route("/edit_Goals/<string:id>", methods=['GET', 'POST'])
def edit_Goals(id):
    user_id = session.get('user_id')

    if request.method == 'POST':
        target_amount = request.form['target_amount']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        goal_description = request.form['goal_description']
        goal_type = request.form['goal_type']
        achieved_amount = request.form.get('Achieved_amount', 0)

        sql = text("""
            UPDATE Savings_goals 
            SET Target_amount = :target_amount, start_date = :start_date, end_date = :end_date, 
                Goal_description = :goal_description, Goal_type = :goal_type, Achieved_amount = :achieved_amount
            WHERE Goal_id = :goal_id AND User_id = :user_id
        """)
        db.session.execute(sql, {
            "target_amount": target_amount,
            "start_date": start_date,
            "end_date": end_date,
            "goal_description": goal_description,
            "goal_type": goal_type,
            "achieved_amount": achieved_amount,
            "goal_id": id,
            "user_id": user_id
        })
        db.session.commit()

        flash("Goal Updated Successfully")
        return redirect(url_for("savings_goals"))

    sql = text("SELECT * FROM Savings_goals WHERE Goal_id = :goal_id")
    goal = db.session.execute(sql, {"goal_id": id}).fetchone()

    return render_template("editgoals.html", datas=goal)


@app.route("/delete_Goals/<string:id>", methods=['POST' , 'GET'])
def delete_Goals(id):
    user_id = session.get('user_id')

    sql = text("DELETE FROM Savings_goals WHERE Goal_id = :goal_id AND User_id = :user_id")
    db.session.execute(sql, {"goal_id": id, "user_id": user_id})
    db.session.commit()

    flash('Goal Deleted Successfully')
    return redirect(url_for("savings_goals"))


@app.route("/restart_goal/<int:goal_id>", methods=["POST"])
def restart_goal(goal_id):
    user_id = session.get("user_id")
    family_head_id = session.get("family_head_id")

    if not user_id or not family_head_id:
        flash("User not logged in or family information unavailable.")
        return redirect(url_for("login"))

    # Fetch the current goal's start_date and end_date
    sql_fetch = text("""
        SELECT start_date, end_date 
        FROM Savings_goals
        WHERE Goal_id = :goal_id AND (User_id = :user_id OR family_head_id = :family_head_id)
    """)
    goal = db.session.execute(sql_fetch, {
        "goal_id": goal_id,
        "user_id": user_id,
        "family_head_id": family_head_id
    }).fetchone()

    if not goal:
        flash("Goal not found.")
        return redirect(url_for("savings_goals"))

    # Calculate the duration of the goal
    original_start_date = goal._mapping["start_date"]
    original_end_date = goal._mapping["end_date"]
    goal_duration = (original_end_date - original_start_date).days

    # Set the new start_date to today and calculate the new end_date
    new_start_date = datetime.now().date()
    new_end_date = new_start_date + timedelta(days=goal_duration)

    # Update the goal: reset achieved amount, set status to 'Active', and update start_date and end_date
    sql_update = text("""
        UPDATE Savings_goals 
        SET Achieved_amount = 0, Goal_status = 'Active', start_date = :new_start_date, end_date = :new_end_date
        WHERE Goal_id = :goal_id AND (User_id = :user_id OR family_head_id = :family_head_id)
    """)
    db.session.execute(sql_update, {
        "new_start_date": new_start_date,
        "new_end_date": new_end_date,
        "goal_id": goal_id,
        "user_id": user_id,
        "family_head_id": family_head_id
    })
    db.session.commit()

    flash("Goal restarted successfully with updated start and end dates!")
    return redirect(url_for("savings_goals"))

@app.route("/progress_bar/<string:id>", methods=["GET"])
def progress_bar(id):
    user_id = session.get("user_id")
    family_head_id = session.get("family_head_id")

    # Fetch goal details
    sql = text("""
        SELECT * FROM Savings_goals 
        WHERE goal_id = :goal_id AND (user_id = :user_id OR family_head_id = :family_head_id)
    """)
    goal = db.session.execute(sql, {"goal_id": id, "user_id": user_id, "family_head_id": family_head_id}).fetchone()

    if not goal:
        flash("Goal not found")
        return redirect(url_for("savings_goals"))

    # Calculate progress percentage with rounding
    achieved_amount = goal._mapping["Achieved_amount"]
    target_amount = goal._mapping["Target_amount"]
    progress_percentage = round((achieved_amount / target_amount) * 100, 2) if target_amount > 0 else 0

    return render_template(
        "progressbar.html",
        goal=goal,
        progress_percentage=progress_percentage
    )

if __name__ == "__main__":
    app.run(debug=True)