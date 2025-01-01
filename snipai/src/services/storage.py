import struct
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from loguru import logger
from PyQt6.QtCore import pyqtSignal, pyqtSlot
from PyQt6.QtGui import QPixmap
from sqlalchemy import func
from sqlmodel import Session, select, text

from snipai.src.common.config import cfg
from snipai.src.common.db import Database
from snipai.src.common.prompt import IMAGE_DESCRIPTION_TO_TAGS_PROMPT
from snipai.src.common.types import TimeFilter
from snipai.src.model.image import Image, ImageTag, Tag
from snipai.src.services.base import BaseService
from snipai.src.services.embed import EmbeddingService
from snipai.src.services.llm import LLMResponse, LLMService


class StorageService(BaseService):
    image_saved = pyqtSignal(str)  # image id
    image_deleted = pyqtSignal(str)
    image_desc_updated = pyqtSignal(str, str)  # id, description
    tag_added = pyqtSignal(str, list)  # image id, [tag id]

    def __init__(self, base_path: str):
        super().__init__()

        self.assets_dir = Path(base_path)
        self.images_dir = self.assets_dir / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)

        # Use moondream to generate image description
        self.init_services()

        Database.init(self.assets_dir)

        self.executor = ThreadPoolExecutor(
            max_workers=3
        )  # For parallel image/metadata saves

        self.start()

    def init_services(self):
        self.image2text = LLMService(model="moondream")
        self.image2text.generation_completed.connect(
            self._update_image_description
        )

        self.imgdesc2tags = LLMService(model="qwen2:1.5b")

        self.any2emb = EmbeddingService()
        self.any2emb.embed_completed.connect(self._save_image_emb)

    def save_screenshot(self, pixmap: QPixmap):
        """Queue screenshot for saving"""
        self._queue.put(pixmap)

    def _process_item(self, item: Union[QPixmap]):
        """Process item in queue. Only image for now, may add others later."""
        if isinstance(item, QPixmap):
            self._process_image(item)

    def _process_image(self, pixmap: QPixmap):
        timestamp = datetime.now()
        filename = f"snip_{timestamp.strftime('%Y-%m-%d')}_{timestamp.strftime('%H.%M.%S')}.png"
        image = Image(
            filename=filename,
            filepath=str(Path(timestamp.strftime("%Y/%m")) / filename),
            timestamp=timestamp,
            width=pixmap.width(),
            height=pixmap.height(),
        )
        # Use thread pool for parallel saving of image and metadata
        future_img = self.executor.submit(self._save_image, pixmap, image)
        future_meta = self.executor.submit(self._save_image_metadata, image)

        # Wait for all operations to complete
        future_img.result()
        future_meta.result()

    def _save_image(self, pixmap: QPixmap, image: Image):
        # Create directory if it doesn't exist
        filepath = self.images_dir / image.filepath
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Save the image
        pixmap.save(str(filepath))

    def _delete_image(self, image: Image):
        """
        Delete an image and all its related data.

        Args:
            image (Image): The image object to delete

        This includes:
        - The actual image file
        - Database record in the image table
        - Related embeddings in image_embedding table
        - Related tags in imagetag table
        """
        try:
            # 1. Delete the actual image file
            image_path = self.images_dir / image.filepath
            if image_path.exists():
                image_path.unlink()

            # 2. Delete from database
            with Database.session() as session:
                # Delete image tags (the relationship will be automatically removed)
                image_db = session.get(Image, image.id)
                if image_db:
                    image_db.tags.clear()
                    session.delete(image_db)

                session.commit()

            # 3. Delete embeddings
            # We need to use raw SQL for the virtual table
            with Database._engine.connect() as conn:
                conn.execute(
                    text(
                        "DELETE FROM image_embedding WHERE image_id = :image_id"
                    ),
                    {"image_id": image.id},
                )
                conn.commit()

            logger.info(f"Successfully deleted image {image.id}")
            self.image_deleted.emit(image.id)

        except Exception as e:
            logger.error(f"Error deleting image {image.id}: {str(e)}")
            raise Exception(f"Failed to delete image: {str(e)}")

    def _save_image_metadata(self, image: Image):
        with Database.session() as session:
            img_full_path = str(self.images_dir / image.filepath)
            # Use moondream to generate description from image.
            self.image2text.generate_response(
                messages=[
                    {
                        "role": "user",
                        "content": "Describe this image, being as detailed as possible, so that when someone reads the description, they can fully understand the image without actually seeing it and labeling it. Include all the texts appear in the image.",
                        "images": [img_full_path],
                    }
                ],
                options={"temperature": 0.1},
                task_id=image.id,
            )

            session.add(image)
            session.commit()
            self.image_saved.emit(image.id)

    def _update_image_description(self, response: LLMResponse):
        """Update the description of an image in the database."""
        image_id = response.task_id
        image_desc = response.message

        tags = self.get_all_tags()
        with Database.session() as session:
            stmt = select(Image).where(Image.id == image_id)
            image = session.exec(stmt).one()
            image.description = image_desc.strip()

            if tags and cfg.enable_ai_tagging:
                # LLM model
                self.imgdesc2tags = self.imgdesc2tags.with_structured_output(
                    model={
                        "$defs": {
                            "TagType": {
                                "enum": [tag.name for tag in tags],
                                "title": "TagType",
                                "type": "string",
                            }
                        },
                        "properties": {
                            "names": {
                                "items": {"$ref": "#/$defs/TagType"},
                                "title": "Names",
                                "type": "array",
                            }
                        },
                        "required": ["names"],
                        "title": "Tags",
                        "type": "object",
                    }
                )
                self.imgdesc2tags.generation_completed.connect(
                    self._save_generated_image_tags_llm
                )
                available_tags = [tag.name for tag in tags]
                self.imgdesc2tags.generate_response(
                    messages=[
                        {
                            "role": "system",
                            "content": IMAGE_DESCRIPTION_TO_TAGS_PROMPT.format(
                                available_tags=available_tags,
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"""## Input: {image_desc}\n\n## Tag list:\n\n{available_tags}\n\nOutput:\n\n""",
                        },
                    ],
                    task_id=image_id,
                )
            session.add(image)
            session.commit()
            session.refresh(image)

            self.image_desc_updated.emit(image.id, image.description)

        self.any2emb.encode(text=image_desc, task_id=image_id)

    def _serialize_embedding(self, vector: List[float]) -> bytes:
        """Serialize embedding vector to bytes format"""
        return struct.pack(f"{len(vector)}f", *vector)

    @pyqtSlot(str, str)
    def _save_image_emb(self, task_id: str, embeddings_str: str):
        """Save or update the embedding representation of an image."""
        # Convert embeddings str to ndarray
        description_embeddings = [
            float(x) for x in embeddings_str.strip("[]").split()
        ]
        serialized_embeddings = self._serialize_embedding(
            description_embeddings
        )

        with Database._engine.connect() as conn:
            # Check if a record with the same image_id exists
            exists_stmt = text(
                "SELECT 1 FROM image_embedding WHERE image_id = :image_id"
            )
            exists = conn.execute(exists_stmt, {"image_id": task_id}).scalar()

            if exists:
                # Update the existing record
                delete_stmt = text(
                    "DELETE FROM image_embedding WHERE image_id = :image_id"
                )
                conn.execute(delete_stmt, {"image_id": task_id})
                logger.info(f"Deleted existing embeddings for image {task_id}")

            # Insert a new record
            insert_stmt = text(
                """
                INSERT INTO image_embedding (vector_id, image_id, description_embedding)
                VALUES (:vector_id, :image_id, :desc_emb)
                """
            )
            conn.execute(
                insert_stmt,
                {
                    "vector_id": str(uuid.uuid4()),
                    "image_id": task_id,
                    "desc_emb": serialized_embeddings,
                },
            )
            logger.info(f"Inserted embeddings for image {task_id}")
            conn.commit()

    @property
    def total_images(self):
        with Database.session() as session:
            count = session.exec(select(func.count(Image.id))).one()
        return count

    def load_image(self, id: str):
        with Database.session() as session:
            statement = select(Image).where(Image.id == id)
            image = session.exec(statement).one()
            return Image(**image.model_dump())

    def _get_image_tags(self, session: Session, image_id: str):
        image = session.exec(select(Image).where(Image.id == image_id)).one()
        return [Tag(**t.model_dump()) for t in image.tags]

    def get_image_tags(self, image_id: str):
        with Database.session() as session:
            return self._get_image_tags(session, image_id=image_id)

    def get_image_tags_batch(
        self, image_ids: List[str]
    ) -> Dict[str, List[Tag]]:
        """Fetch tags for multiple images in a single query."""
        with Database.session() as session:
            # Query to get all tags for the specified images
            query = (
                select(ImageTag, Tag)
                .join(Tag)
                .where(ImageTag.image_id.in_(image_ids))
                .order_by(Tag.name)
            )
            results = session.exec(query).all()

            # Organize results by image_id
            tags_by_image = {}
            for image_tag, tag in results:
                if image_tag.image_id not in tags_by_image:
                    tags_by_image[image_tag.image_id] = []
                tags_by_image[image_tag.image_id].append(
                    Tag(**tag.model_dump())
                )

            return tags_by_image

    def _save_generated_image_tags_llm(self, response: LLMResponse):
        if _tags := response.response.get("names"):
            tags_name = set(_tags)

            tags = [
                Tag(is_generated=True, name=tag_name) for tag_name in tags_name
            ]
            logger.warning(f"Tagging by LLM is done - response: {tags_name}")
            with Database.session() as session:
                return self._update_image_tags(
                    session, image_id=response.task_id, updated_tags=tags
                )

    def _update_image_tags(
        self, session: Session, image_id: str, updated_tags: List[Tag]
    ):
        """Update the list of tags for an image, replacing existing tags"""
        image = session.exec(select(Image).where(Image.id == image_id)).one()

        # Tag list didn't change, thus no update.
        if set(t.id for t in image.tags) == set(t.id for t in updated_tags):
            return None

        if not updated_tags:  # This handles both None and []
            image.tags.clear()
            session.add(image)
            session.commit()
            self.tag_added.emit(image_id, [])
            return Image(**image.model_dump())

        # Clear existing tags
        image.tags.clear()

        # Add all selected tags
        for tag in updated_tags:
            # Check if tag already exists in database
            db_tag = session.exec(
                select(Tag).where(Tag.name == tag.name)
            ).first()
            if db_tag:
                # Use existing tag from database
                image.tags.append(db_tag)
            else:
                # Create new tag
                session.add(tag)
                image.tags.append(tag)

        session.add(image)
        session.commit()

        self.tag_added.emit(image_id, [tag.id for tag in updated_tags])
        return Image(**image.model_dump())

    def update_image_tags(self, image_id: str, updated_tags: List[Tag]):
        with Database.session() as session:
            return self._update_image_tags(
                session, image_id=image_id, updated_tags=updated_tags
            )

    def get_all_tags(self, with_count: bool = False):
        """Get all tags, optionally including the count of images per tag."""
        with Database.session() as session:
            if with_count:
                # Query that includes the count of images per tag
                query = (
                    select(
                        Tag, func.count(ImageTag.image_id).label("image_count")
                    )
                    .outerjoin(ImageTag)
                    .group_by(Tag.id)
                    .order_by(Tag.name)
                )
                results = session.exec(query).all()
                return [
                    (Tag(**tag.model_dump()), count) for tag, count in results
                ]
            else:
                # Original query without counts
                tags = session.exec(select(Tag).order_by(Tag.name)).all()
                return [Tag(**t.model_dump()) for t in tags]

    def update_tags(self, tags: List[str]):
        """Update"""
        if not tags:
            return
        with Database.session() as session:
            existing_tags = session.exec(select(Tag)).all()
            existing_names = {t.name for t in existing_tags}

            # Add new tags
            for tag_name in tags:
                if tag_name not in existing_names:
                    new_tag = Tag(
                        name=tag_name,
                        is_generated=False,  # User-created tags
                    )
                    session.add(new_tag)

            # Remove tags that are no longer in the config
            for tag in existing_tags:
                if tag.name not in tags:
                    session.delete(tag)

            session.commit()

    def _hybrid_search_images(
        self,
        conn,
        query: str = None,
        time_start: Optional[datetime] = None,
        time_end: Optional[datetime] = None,
        tags: List[str] = None,
        page: int = 0,
        per_page: int = 42,
    ):
        # TODO: re-implement filename search
        # TODO: fix a bug where the number of returned images is not per_page
        if query:
            # When we have a query, use the full hybrid search
            base_query = """
            WITH VectorScores AS (
                SELECT 
                    i.*,
                    vec_distance_cosine(description_embedding, :embedding) as rank
                FROM image i
                INNER JOIN image_embedding ie ON i.id = ie.image_id
            ),
            FilteredImages AS (
                SELECT DISTINCT *
                FROM VectorScores
            """
            if tags:
                base_query += """
                INNER JOIN imagetag it ON i.id = it.image_id
                INNER JOIN tag t ON it.tag_id = t.id AND t.name IN (:tags)
                """

            query_embeddings = self.any2emb._encode(
                query.strip(), retrieval=True
            )[0]
            params = {
                "embedding": self._serialize_embedding(
                    query_embeddings.tolist()
                ),
            }
        else:
            # When no query, just return all images ordered by timestamp
            base_query = """
            WITH FilteredImages AS (
                SELECT DISTINCT
                    i.*,
                    1.0 as rank
                FROM image i
            """
            if tags:
                base_query += """
                INNER JOIN imagetag it ON i.id = it.image_id
                INNER JOIN tag t ON it.tag_id = t.id AND t.name IN (:tags)
                """
            base_query += "WHERE 1=1"
            params = {}

        # Add tag filtering parameters if tags are provided
        if tags:
            if len(tags) == 1:
                base_query = base_query.replace(
                    "t.name IN (:tags)", "t.name = :tags"
                )
                params["tags"] = tags[0]
            else:
                # Create individual parameters for each tag
                tag_params = {f"tag_{i}": tag for i, tag in enumerate(tags)}
                # Replace :tags with individual parameter names
                tag_in_clause = ",".join(f":tag_{i}" for i in range(len(tags)))
                base_query = base_query.replace(
                    "t.name IN (:tags)", f"t.name IN ({tag_in_clause})"
                )
                params.update(tag_params)

        # Add time filter conditions
        if time_start:
            base_query += " AND i.created_at >= :time_start"
            params["time_start"] = time_start
        if time_end:
            base_query += " AND i.created_at <= :time_end"
            params["time_end"] = time_end

        # Close the CTE and add ordering and pagination
        stmt = f"""
            {base_query}
        ),
        TotalCount AS (
            SELECT COUNT(*) as total_count 
            FROM FilteredImages
        ),
        PaginatedResults AS (
            SELECT *
            FROM FilteredImages
            ORDER BY rank ASC, timestamp DESC
            LIMIT :limit OFFSET :offset
        )
        SELECT 
            r.*,
            c.total_count
        FROM PaginatedResults r
        CROSS JOIN TotalCount c;
        """

        # Add pagination parameters
        params.update({"limit": per_page, "offset": page * per_page})

        # Execute the query
        logger.info(f"Final SQL query: {stmt} - {params}")
        results = conn.execute(text(stmt), params).fetchall()

        # Extract total count from the first row (they all have the same count)
        total_count = results[0][-1] if results else 0

        # Convert to list of Image objects (excluding the count column)
        images = [
            Image(
                **{
                    k: v
                    for k, v in dict(row._mapping).items()
                    if k != "total_count"
                }
            )
            for row in results
        ]
        return images, total_count

    def hybrid_search_images(
        self,
        query: str = None,
        time_filter: TimeFilter = None,
        tags: List[str] = None,
        page: int = 0,
        per_page: int = 42,
    ) -> Tuple[List[Image], int]:
        """
        Performs a combined search using vector similarity, traditional filtering, and tag matching.

        Args:
            query: Search query string for semantic and filename search
            time_filter: TimeFilter enum for filtering by date
            tags: List of tags to filter by (all tags must match)
            page: Page number for pagination
            per_page: Number of items per page

        Returns:
            List[Image]: List of matched images
        """
        # Add time filter conditions
        if time_filter:
            time_start, time_end = time_filter.to_date_range()
        else:
            time_start, time_end = None, None

        with Database._engine.connect() as conn:
            return self._hybrid_search_images(
                conn=conn,
                query=query,
                time_start=time_start,
                time_end=time_end,
                tags=tags,
                page=page,
                per_page=per_page,
            )

    def compute_similarity(self, image_id1: str, image_id2: str) -> float:
        """Compute cosine similarity between two images' description embeddings."""
        with Database._engine.connect() as conn:
            query = text("""
                SELECT vec_distance_cosine(e1.description_embedding, e2.description_embedding) as similarity
                FROM image_embedding e1, image_embedding e2
                WHERE e1.image_id = :id1 AND e2.image_id = :id2
            """)
            result = conn.execute(
                query, {"id1": image_id1, "id2": image_id2}
            ).scalar()
            return float(result) if result is not None else 0.0
