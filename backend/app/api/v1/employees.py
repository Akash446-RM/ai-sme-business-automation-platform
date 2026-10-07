"""Employee management endpoints."""

from __future__ import annotations

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query, status

from app.core.deps import CurrentUser, DbSession, require_manager
from app.core.pagination import Page, PageParams, page_params
from app.models.user import User
from app.schemas.common import Message
from app.schemas.employee import (
    EmployeeCreate,
    EmployeePerformance,
    EmployeeRead,
    EmployeeUpdate,
)
from app.services.employee_service import EmployeeService

router = APIRouter(prefix="/employees", tags=["employees"])

ManagerDep = Annotated[User, Depends(require_manager)]


@router.get("", response_model=Page[EmployeeRead], summary="List employees")
def list_employees(
    db: DbSession,
    _: CurrentUser,
    params: Annotated[PageParams, Depends(page_params)],
    search: Optional[str] = Query(None, max_length=100),
    role: Optional[str] = Query(None, max_length=60),
    department: Optional[str] = Query(None, max_length=60),
    is_active: Optional[bool] = None,
    sort_by: str = Query("name", pattern="^(name|employee_code|role|hired_on|created_at)$"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
) -> Page[EmployeeRead]:
    employees, total = EmployeeService(db).list_employees(
        params,
        search=search,
        role=role,
        department=department,
        is_active=is_active,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return Page.create(
        [EmployeeRead.model_validate(employee) for employee in employees], total, params
    )


@router.get("/roles", response_model=List[str], summary="Distinct employee roles")
def list_roles(db: DbSession, _: CurrentUser) -> List[str]:
    return EmployeeService(db).roles()


@router.get("/{employee_id}", response_model=EmployeeRead, summary="Get one employee")
def get_employee(employee_id: int, db: DbSession, _: CurrentUser) -> EmployeeRead:
    return EmployeeRead.model_validate(EmployeeService(db).get(employee_id))


@router.get(
    "/{employee_id}/performance",
    response_model=EmployeePerformance,
    summary="Sales performance for an employee",
)
def employee_performance(
    employee_id: int, db: DbSession, _: CurrentUser
) -> EmployeePerformance:
    return EmployeeService(db).performance(employee_id)


@router.post(
    "",
    response_model=EmployeeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an employee",
)
def create_employee(payload: EmployeeCreate, db: DbSession, _: ManagerDep) -> EmployeeRead:
    return EmployeeRead.model_validate(EmployeeService(db).create(payload))


@router.put("/{employee_id}", response_model=EmployeeRead, summary="Update an employee")
def update_employee(
    employee_id: int, payload: EmployeeUpdate, db: DbSession, _: ManagerDep
) -> EmployeeRead:
    return EmployeeRead.model_validate(EmployeeService(db).update(employee_id, payload))


@router.post(
    "/{employee_id}/deactivate",
    response_model=EmployeeRead,
    summary="Deactivate an employee",
)
def deactivate_employee(employee_id: int, db: DbSession, _: ManagerDep) -> EmployeeRead:
    return EmployeeRead.model_validate(EmployeeService(db).deactivate(employee_id))


@router.delete("/{employee_id}", response_model=Message, summary="Delete an employee")
def delete_employee(employee_id: int, db: DbSession, _: ManagerDep) -> Message:
    EmployeeService(db).delete(employee_id)
    return Message(message="Employee deleted successfully.")
