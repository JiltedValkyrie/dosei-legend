/* Included by recomp.c: use the existing level-select/spawn and pad paths. */
/* Read-only telemetry, found by symbol in the exact diagnostic ELF. Keeping
 * this out of the command mailbox preserves the existing trace wire layout. */
static volatile uint32_t control_environment[6];
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
            recomp_link.x = m->pose[0];
            recomp_link.y = m->pose[1] + RECOMP_LINK_EYE_HEIGHT;
            recomp_link.z = m->pose[2];
            recomp_link_yaw = (uint16_t)m->pose[3];
            link_safe_position = recomp_link;
            link_fall_peak_y = recomp_link.y;
            link_anim_pose(LINK_CLIP_IDLE, 0, 0);
            player_input_reset();
            oot_follow_set_legacy(m->legacy != 0);
            snap_camera_to_link();
            recomp_camera.x = m->camera[0];
            recomp_camera.y = m->camera[1];
            recomp_camera.z = m->camera[2];
            recomp_yaw = (uint16_t)m->camera[3];
            recomp_pitch = m->camera[4];
            m->remaining = 0;
        } else if (m->opcode == 2 && m->steps <= 600) {
            m->remaining = m->steps;
        } else if (m->opcode == 3) {
            oot_follow_set_legacy(m->legacy != 0);
            snap_camera_to_link();
        } else if (m->opcode == 4) {
            m->remaining = 0;
        } else if (m->opcode == 5 && (unsigned)m->pose[0] <= 65535u &&
                   (unsigned)m->pose[1] <= 65535u) {
            save_state.day_time = (uint16_t)m->pose[0];
            oot_core_clock_reset((unsigned)m->pose[1]);
            m->remaining = 0;
        } else m->error = 2;
        m->ack = m->request;
    }
    /* VBlank does not advance the diagnostic clock. One requested step is
     * exactly one normal 30 Hz update, irrespective of emulator/host speed. */
    if (m->remaining) {
        --m->remaining; ++m->sim_steps; ticks += 2;
        /* Start has its own edge latch outside player_input. Match VBlank's
         * normal producer so the probe can exercise the real pause path. */
        input_edge_sample(&start_edge, (m->buttons & CAMERA_START) != 0);
        player_input_sample_pad((uint16_t)m->buttons, true,
                                (uint8_t)m->axis_x, (uint8_t)m->axis_y);
    }
}

static void control_end(void)
{
    volatile control_mailbox_t *m = CONTROL;
    control_environment[0] = save_state.day_time;
    control_environment[1] = oot_core_skybox_time();
    control_environment[2] = gameplay_is_paused();
    control_environment[3] = game_mode();
    control_environment[4] = save_state.total_days;
    control_environment[5] = save_state.bgs_day_count;
    m->link_now[0] = recomp_link.x;
    m->link_now[1] = recomp_link.y - RECOMP_LINK_EYE_HEIGHT;
    m->link_now[2] = recomp_link.z;
    m->link_now[3] = recomp_link_yaw;
    m->camera_now[0] = recomp_camera.x;
    m->camera_now[1] = recomp_camera.y;
    m->camera_now[2] = recomp_camera.z;
    m->camera_now[3] = recomp_yaw;
    m->camera_now[4] = recomp_pitch;
}
