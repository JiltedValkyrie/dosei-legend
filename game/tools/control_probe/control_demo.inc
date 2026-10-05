/* Included by demo.c: use the existing level-select/spawn and pad paths. */
static void __attribute__((optimize("Os"))) control_begin(void)
{
    volatile control_mailbox_t *m = CONTROL;
    if (m->magic != CONTROL_MAGIC) {
        memset((void *)m, 0, sizeof(*m));
        m->version = 1; m->bytes = sizeof(*m);
        m->axis_x = m->axis_y = 128;
        m->hud = 1;
        level_select_open();
        game_mode_set(GAME_MODE_FILE_SELECT);
        level_select.scene = SCENE_SPOT00;
        level_select.room = 0;
        level_select.max_gear = true;
        level_select.adult = true;
        level_select_enter();
        if (level_select.failed || game_mode() != GAME_MODE_PLAY) m->error = 1;
        link_anim_pose(LINK_CLIP_IDLE, 0, 0);
        jo_clear_screen();
        slScrAutoDisp(NBG0ON);
        m->magic = CONTROL_MAGIC; /* publish only after setup */
    }
    ++m->frame;
    if (m->request != m->ack) {
        m->error = 0;
        if (m->opcode == 1) {
            /* Reinitialize movement state before positioning; y is FEET. */
            place_at_spawn(SCENE_SPOT00, 0);
            gameplay_reset();
            demo_link.x = m->pose[0];
            demo_link.y = m->pose[1] + DEMO_LINK_EYE_HEIGHT;
            demo_link.z = m->pose[2];
            demo_link_yaw = (uint16_t)m->pose[3];
            link_safe_position = demo_link;
            link_fall_peak_y = demo_link.y;
            link_anim_pose(LINK_CLIP_IDLE, 0, 0);
            player_input_reset();
            oot_follow_set_legacy(m->legacy != 0);
            snap_camera_to_link();
            demo_camera.x = m->camera[0];
            demo_camera.y = m->camera[1];
            demo_camera.z = m->camera[2];
            demo_yaw = (uint16_t)m->camera[3];
            demo_pitch = m->camera[4];
            m->remaining = 0;
        } else if (m->opcode == 2 && m->steps <= 600) {
            m->remaining = m->steps;
        } else if (m->opcode == 3) {
            oot_follow_set_legacy(m->legacy != 0);
            snap_camera_to_link();
        } else if (m->opcode == 4) {
            m->remaining = 0;
        } else m->error = 2;
        m->ack = m->request;
    }
    /* VBlank does not advance the diagnostic clock. One requested step is
     * exactly one normal 30 Hz update, irrespective of emulator/host speed. */
    if (m->remaining) {
        --m->remaining; ++m->sim_steps; ticks += 2;
        player_input_sample_pad((uint16_t)m->buttons, true,
                                (uint8_t)m->axis_x, (uint8_t)m->axis_y);
    }
}

static void control_end(void)
{
    volatile control_mailbox_t *m = CONTROL;
    m->link_now[0] = demo_link.x;
    m->link_now[1] = demo_link.y - DEMO_LINK_EYE_HEIGHT;
    m->link_now[2] = demo_link.z;
    m->link_now[3] = demo_link_yaw;
    m->camera_now[0] = demo_camera.x;
    m->camera_now[1] = demo_camera.y;
    m->camera_now[2] = demo_camera.z;
    m->camera_now[3] = demo_yaw;
    m->camera_now[4] = demo_pitch;
}
