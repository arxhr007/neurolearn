"""Seed the database with Eva (student1) and her teacher with full profile + memories."""

from datetime import datetime

from app.database import SessionLocal, init_db
from app.models.memory import StudentMemory
from app.models.user import Student, Teacher
from app.services.auth import hash_password


def main() -> None:
    init_db()

    with SessionLocal() as db:
        existing_teacher = db.query(Teacher).filter(Teacher.username == "teacher1").first()
        if existing_teacher:
            teacher = existing_teacher
            print(f"Teacher already exists: {teacher.username}")
        else:
            teacher = Teacher(
                username="teacher1",
                password_hash=hash_password("teacher123"),
                full_name="Teacher User",
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(teacher)
            db.flush()
            print(f"Created teacher: {teacher.username} (id={teacher.id})")

        existing_student = db.query(Student).filter(Student.username == "student1").first()
        if existing_student:
            student = existing_student
            print(f"Student already exists: {student.username}")
        else:
            student = Student(
                student_id="s100",
                username="student1",
                password_hash=hash_password("student123"),
                full_name="Eva",
                age=10,
                reading_age=16,
                learning_style="analogy-heavy",
                interests=["chess", "football"],
                neuro_profile=["adhd", "dyslexia"],
                father_name="Binu",
                mother_name="Regy",
                grandfather_name="Emil",
                grandmother_name="Ema",
                favorite_color="Blue",
                teacher_name="Esha",
                place="Thrissur",
                friends="shayen, aaron",
                favorite_food="Payasam",
                favorite_animal="Cat",
                favorite_interest="Reading",
                is_active=True,
                teacher_id=teacher.id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(student)
            db.flush()
            print(f"Created student: {student.username} (id={student.id}, student_id={student.student_id})")

        existing_count = db.query(StudentMemory).filter(StudentMemory.student_id == student.id).count()
        if existing_count > 0:
            print(f"Student already has {existing_count} memories — skipping seed")
        else:
            memories = [
                StudentMemory(
                    student_id=student.id,
                    text=(
                        "എന്റെ അമ്മ റെഗിയും അച്ഛൻ ബിനുവും എല്ലാ ഞായറാഴ്ചയും പായസം ഉണ്ടാക്കും. "
                        "ഞാൻ അമ്മയോടൊപ്പം അടുക്കളയിൽ നിന്ന് പായസം ഉണ്ടാക്കാൻ സഹായിക്കും. "
                        "അച്ഛൻ പാലും പഞ്ചസാരയും എടുത്തു തരും. ഞങ്ങൾ മൂന്നുപേരും ഒന്നിച്ച് ഇരുന്ന് പായസം കഴിക്കും. "
                        "അത് വളരെ രുചിയുള്ളതാണ്. ഞായറാഴ്ച വരുന്നത് ഞാൻ കാത്തിരിക്കും."
                    ),
                    category="FAMILY",
                    title="Sunday Payasam Tradition in Thrissur",
                    summary="Eva's family makes Payasam every Sunday in Thrissur.",
                    emotions='["happy", "nostalgic"]',
                    people="Regy,Binu",
                    places="Thrissur,Home,Kitchen",
                    activities="cooking, eating together",
                    tags="payasam, sunday, family tradition",
                    importance_score=4,
                ),
                StudentMemory(
                    student_id=student.id,
                    text=(
                        "എന്റെ വീടിന് മുന്നിൽ ഒരു വലിയ മുറ്റമുണ്ട്. അവിടെ ഞാനും എന്റെ കൂട്ടുകാരായ "
                        "ഷായേനും ആരോണും ഒന്നിച്ച് കളിക്കും. ഞങ്ങൾ പന്ത് കളിയും കണ്ണുമൂടിക്കളിയും "
                        "കളിക്കും. വലിയ മാവിൻ്റെ ചുവട്ടിൽ ഞങ്ങൾ ഒളിച്ചും കളിക്കും. "
                        "വൈകുന്നേരമായാൽ ഞങ്ങൾക്ക് വീട്ടിലേക്ക് പോകാൻ മനസ്സ് വരില്ല."
                    ),
                    category="PERSONAL",
                    title="Playing in the Front Yard with Friends",
                    summary="Eva plays in the front yard with friends Shayen and Aaron.",
                    emotions='["happy", "excited"]',
                    people="Shayen,Aaron",
                    places="Home, Front Yard",
                    activities="playing ball, hide-and-seek",
                    tags="friends, front yard, mango tree",
                    importance_score=3,
                ),
                StudentMemory(
                    student_id=student.id,
                    text=(
                        "ഞായറാഴ്ച ഞാൻ അമ്മയോടും അച്ഛനോടും ഒപ്പം എന്റെ അമ്മൂമ്മയുടെ വീട്ടിലേക്ക് പോകും. "
                        "അവിടെ ഒരു വെളുത്ത പൂച്ചയുണ്ട്, അതിന്റെ പേര് മിന്നു. "
                        "ഞാൻ മിന്നുവിനൊപ്പം കളിക്കും. അമ്മൂമ്മ എനിക്ക് മാങ്ങ തരും. "
                        "ഞാൻ അമ്മൂമ്മയുടെ കൂടെ പൂന്തോട്ടത്തിൽ പൂവിന് വെള്ളം ഒഴിക്കും."
                    ),
                    category="FAMILY",
                    title="A Visit to Grandmother's House",
                    summary="Eva visits her grandmother's house, plays with the cat Minnu, eats mangoes, and waters plants.",
                    emotions='["happy", "content"]',
                    people="Mother,Father,Grandmother,Minnu",
                    places="Grandmother's House, Garden",
                    activities="playing with cat, eating mango, watering plants",
                    tags="grandmother, cat, sunday visit",
                    importance_score=3,
                ),
            ]
            for m in memories:
                db.add(m)
            db.commit()
            print(f"Created {len(memories)} memories for {student.full_name}")

    print("Done seeding Eva's data.")


if __name__ == "__main__":
    main()
